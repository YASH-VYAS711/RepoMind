# backend/rag/llm_pipeline.py

from typing import List, Dict
import requests
import json
import time
import re
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, REPOS_DIR
from rag.retriever import retrieve_chunks
from pathlib import Path
# ──────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────

# Max characters we pass to LLM as context
# Too low = missing info. Too high = LLM gets confused + slower
MAX_CONTEXT_CHARS = 8000

# ──────────────────────────────────────────────────────────
# MODE DETECTION
# ──────────────────────────────────────────────────────────
def make_relative_path(file_path: str, repo_id: str) -> str:
    """
    Convert absolute path to relative path from repo root.

    Before: C:\\Users\\yash\\...\\c8e3c9298ef1\\Backend\\main.py
    After:  Backend/main.py

    Why: Saves ~70 chars per chunk in context window.
    Also makes LLM answers cleaner — "Backend/main.py" not a full Windows path.
    """
    try:
        repo_root = REPOS_DIR / repo_id
        relative = Path(file_path).relative_to(repo_root)
        return str(relative).replace("\\", "/")
    except Exception:
        # If relative conversion fails, just return the filename
        return Path(file_path).name

OVERVIEW_KEYWORDS = {
    "overview", "summary", "what is this", "what does this",
    "explain this", "describe this", "what is the project",
    "what does the project", "introduce", "introduction",
    "high level", "overall", "tell me about", "architecture",
    "explain project", "purpose", "project"
}

def detect_mode(question: str) -> str:
    """
    Returns 'overview' for high-level questions,
    'normal' for specific technical questions.
    
    Why this matters:
    - overview → inject README, skip semantic search
    - normal   → pure semantic search over code chunks
    """
    q = question.lower()
    for keyword in OVERVIEW_KEYWORDS:
        if keyword in q:
            return "overview"
    return "normal"


# ──────────────────────────────────────────────────────────
# CONTEXT BUILDER
# ──────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    text = text.strip()

    # if ends properly → keep
    if text.endswith(('.', '!', '?')):
        return text

    # try to cut to last sentence
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) > 1:
        return " ".join(sentences[:-1])

    # fallback → trim last word
    return text if " " not in text else text.rsplit(" ", 1)[0]

def build_context(chunks: List[Dict], repo_id: str) -> str:
    """
    Structured context grouped by folder type.
    Uses relative paths to save context budget.
    Single shared character budget across all sections.
    """
    
    groups = {"readme": [], "backend": [], "frontend": [], "other": []}

    for chunk in chunks:
        t = chunk.get("type", "other")
        if t not in groups:
            t = "other"
        groups[t].append(chunk)

    context = ""
    total_chars = 0

    for section_name in ["readme", "backend", "frontend", "other"]:
        section_chunks = groups[section_name]
        if not section_chunks:
            continue

        header = f"\n===== {section_name.upper()} =====\n"
        if total_chars + len(header) > MAX_CONTEXT_CHARS:
            break

        context += header
        total_chars += len(header)

        for chunk in section_chunks:
            abs_path = chunk["metadata"].get("file_path", "unknown")
            rel_path = make_relative_path(abs_path, repo_id)
            score = chunk.get("score", -1)
            score_label = "(pinned)" if score < 0 else f"(rel: {1 - score:.2f})"

            content = clean_text(chunk["content"])

            part = f"\nFile: {rel_path} {score_label}\n"
            part += content + "\n"

            if total_chars + len(part) > MAX_CONTEXT_CHARS:
                print(f"[INFO] Budget exhausted in {section_name}")
                break

            context += part
            total_chars += len(part)

    print(f"[INFO] Final context: {total_chars} chars")
    return context
# ──────────────────────────────────────────────────────────
# PROMPT BUILDER
# ──────────────────────────────────────────────────────────

OVERVIEW_PROMPT = """
You are a senior software engineer reviewing a codebase for the first time.

Give a clear project overview structured as:
1. What this project does (1-2 sentences)
2. Tech stack (languages, frameworks, databases)
3. Key components (list the main files/folders and their roles)
4. How the parts connect (data flow or architecture summary)

Use ONLY the provided context. If something is unclear from the context, say so.
Do not make up details.

Context:
{context}

Question:
{question}

Answer:
"""


NORMAL_PROMPT = """
You are a code search engine. Answer ONLY from the provided context.

HARD RULES:
1. Never write code that isn't copied verbatim from the context.
2. Never say "typically", "generally", "usually", "would", "might".
3. Cite the exact relative file path for every claim.
4. If the answer is truly absent, say: "I could not find this in the provided context."

Context:
{context}

Question:
{question}

Answer (cite exact files and quote relevant lines):
"""

def build_prompt(question: str, context: str, mode: str) -> str:
    """
    Choose prompt template based on query mode.
    
    Why two prompts?
    - Overview prompt guides LLM to structure a project summary
    - Normal prompt guides LLM to be precise and cite exact files
    """
    if mode == "overview":
        return OVERVIEW_PROMPT.format(context=context, question=question)
    return NORMAL_PROMPT.format(context=context, question=question)


# ──────────────────────────────────────────────────────────
# OLLAMA STREAMING CALL
# ──────────────────────────────────────────────────────────

def call_ollama(prompt: str):
    """
    Stream response from local Ollama model token by token.
    
    Yields each token as a string.
    Raises exception with clear message if Ollama isn't running.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"

    try:
        response = requests.post(
            url,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True
            },
            stream=True,
            timeout=120   # fail after 2 min if Ollama is frozen
        )
    except requests.exceptions.ConnectionError:
        raise Exception(
            "Cannot connect to Ollama. Make sure it's running: `ollama serve`"
        )

    if response.status_code != 200:
        raise Exception(f"Ollama returned status {response.status_code}")

    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            token = chunk.get("response", "")
            yield token
            if chunk.get("done"):
                break


# ──────────────────────────────────────────────────────────
# MAIN PIPELINE
# ──────────────────────────────────────────────────────────

def ask_question(question: str, repo_id: str) -> str:
    """
    Full RAG pipeline:
    1. Detect query mode (overview vs normal)
    2. Retrieve relevant chunks from ChromaDB
    3. Build structured context string
    4. Build mode-appropriate prompt
    5. Stream answer from Ollama
    
    Returns the complete answer as a string.
    """
    start_total = time.time()

    # ─── Step 1: Detect mode ──────────────────────────────
    mode = detect_mode(question)
    print(f"[INFO] Query mode: {mode}")

    # ─── Step 2: Retrieve chunks ──────────────────────────
    # Overview: k=8 because we want broad project context
    # Normal:   k=5 for precise targeted retrieval
    t1 = time.time()
    k = 8 if mode == "overview" else 8

    # Expand query with technical synonyms before retrieval
    search_query = question
    chunks = retrieve_chunks(search_query, repo_id, k=k, mode=mode)
    t2 = time.time()
    print(f"[TIME] Retrieval: {t2 - t1:.2f}s")
    if not chunks:
        yield "No relevant information found in this repository."
        return
    # ─── Step 3: Build context ────────────────────────────
    context = build_context(chunks, repo_id) 
    print(f"[INFO] Context length: {len(context)} chars")
    prompt = build_prompt(question, context, mode)

    # ─── Step 5: Stream LLM response ─────────────────────
    t7 = time.time()

    try:
        for token in call_ollama(prompt):
            yield token  # live stream in terminal
    except Exception as e:
        print(f"\n[ERROR] LLM call failed: {e}")
        yield f"Error generating answer: {str(e)}"

    t8 = time.time()
    print(f"\n[TIME] LLM: {t8 - t7:.2f}s")
    print(f"[TIME] TOTAL: {time.time() - start_total:.2f}s")
