from typing import List, Dict
from langchain_chroma import Chroma

from config import CHROMA_DIR, TOP_K, REPOS_DIR
from rag.embedder import get_embedding_model
import re
import time
from pathlib import Path
# ──────────────────────────────────────────────────────────
# QUERY EXPANSION (GENERIC CONCEPT → CODE BRIDGE)
# ──────────────────────────────────────────────────────────

CONCEPT_EXPANSIONS = {
    "api": ["axios", "fetch", "request", "agent", "http", "rest", "endpoint"],
    "state": ["reducer", "store", "dispatch", "action", "redux", "context"],
    "route": ["router", "routes", "navigation", "path", "browserrouter"],
    "auth": ["jwt", "token", "login", "authorize", "bearer", "middleware"],
    "config": ["env", "process.env", "settings", "config", "constant"],
    "database": ["db", "model", "schema", "mongoose", "prisma", "sql"],
    "frontend": ["component", "ui", "view", "jsx"],
    "backend": ["server", "controller", "service"]
}


def extract_filename(query: str) -> str | None:
    match = re.search(
        r'\b([\w\-]+\.(py|js|ts|jsx|tsx|java|go|rs|md|toml|yaml|yml|json|env|sh|sql|cpp|c|cs|rb|php))\b',
        query,
        re.IGNORECASE
    )
    return match.group(0).lower() if match else None

def expand_query(query: str) -> str:
    q = query.lower()
    extra_terms = []

    for concept, terms in CONCEPT_EXPANSIONS.items():
        if concept in q:
            extra_terms.extend(terms)

    if extra_terms:
        return f"{query} {' '.join(set(extra_terms))}"
    
    return query
# ──────────────────────────────────────────────────────────
# LOAD VECTOR STORE
# ──────────────────────────────────────────────────────────
NOISE_FILES = {
    "postcss.config.js",
    "postcss.config.ts", 
    "tailwind.config.js",
    "tailwind.config.ts",
    "eslint.config.js",
    ".eslintrc.js",
    ".prettierrc",
    "jest.config.js",
    "babel.config.js",
    ".gitignore",
    ".editorconfig",
}
def get_vector_store(repo_id: str):
    embedding_model = get_embedding_model()

    repo_path = CHROMA_DIR / repo_id

    return Chroma(
        persist_directory=str(repo_path),
        embedding_function=embedding_model
    )


# ──────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────

def get_folder_type(file_path: str, repo_id: str = None) -> str:
    """
    Determine folder type using only the path AFTER the repo hash.
    Prevents RepoMind's own /backend/ folder from poisoning classification.
    """
    path = file_path.lower().replace("\\", "/")

    # If repo_id provided, slice path after the hash
    if repo_id:
        try:
            idx = path.index(repo_id.lower())
            path = path[idx + len(repo_id):]  # everything after the hash
        except ValueError:
            pass  # fallback to full path

    # Now "backend"/"frontend" refer to the CLONED repo's folders only
    if "readme" in path:
        return "readme"
    elif "frontend" in path:
        return "frontend"
    elif "backend" in path:
        return "backend"
    else:
        return "other"

# ──────────────────────────────────────────────────────────
# 🔥 DIRECT README FETCH (NO SEMANTIC SEARCH)
# ──────────────────────────────────────────────────────────

def get_best_readme_chunk(repo_id: str) -> List[Dict]:
    """
    Fetch README content directly without vector search.

    Strategy:
    - Always include root README (most important, up to 3000 chars)
    - Also include backend/README if it exists (up to 1000 chars)
    - Sort by path length so root README is always first
    """
    repo_path = REPOS_DIR / repo_id

    if not repo_path.exists():
        print("[ERROR] Repo path does not exist")
        return []

    readme_files = list(repo_path.rglob("*README*"))

    if not readme_files:
        return []

    # Sort by path length — shortest = closest to root
    readme_files.sort(key=lambda x: len(str(x)))

    results = []

    for i, readme_file in enumerate(readme_files):
        # Skip alembic/migrations README — never useful
        if "alembic" in str(readme_file).lower():
            continue
        if "migration" in str(readme_file).lower():
            continue

        try:
            content = readme_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"[ERROR] Failed to read {readme_file}: {e}")
            continue

        # Root README gets more chars, nested ones get less
        max_chars = 3000 if i == 0 else 800
        content = content[:max_chars]

        if not content.strip():
            continue

        results.append({
            "content": content,
            "metadata": {"file_path": str(readme_file)},
            "score": -1.0,   # sentinel: manually pinned, not from vector search
            "type": "readme"
        })

        # Max 2 README chunks — root + one nested
        if len(results) >= 2:
            break

    return results

def keyword_boost(chunk: Dict, query: str) -> float:
    score = chunk["score"]
    content = chunk["content"].lower()
    file_name = Path(chunk["metadata"].get("file_path", "")).name.lower()
    q = query.lower()

    keywords = []
    if "api" in q:
        keywords += ["@app", "router", "endpoint", "route"]
    if "auth" in q:
        keywords += ["auth", "jwt", "token"]
    if "database" in q:
        keywords += ["sql", "db", "database", "session"]

    for kw in keywords:
        if kw in content:
            score -= 0.05

    # ── NEW: boost connection-relevant config files ──────
    if any(x in q for x in ["connect", "proxy", "api", "baseurl", "fetch", "axios"]):
        if file_name in {"vite.config.js", "vite.config.ts", "next.config.js"}:
            score -= 0.15   # strong pull toward top
        if file_name in {".env", ".env.example"}:
            score -= 0.10

    return score
# ──────────────────────────────────────────────────────────
# RETRIEVE
# ──────────────────────────────────────────────────────────

def retrieve_chunks(query: str, repo_id: str, k: int = None, mode: str = "normal") -> List[Dict]:

    if k is None:
        k = TOP_K
    filename = extract_filename(query)

    if filename:
        print(f"[INFO] File-specific query detected: {filename}")

        vector_store = get_vector_store(repo_id)

        all_docs = vector_store.get(
            where={
                "$and": [
                    {"file_name": filename},
                    {"repo_id": repo_id}
                ]
            }
        )

        if all_docs and all_docs.get("documents"):
            file_chunks = []

            for i, content in enumerate(all_docs["documents"]):
                metadata = all_docs["metadatas"][i]
                path = metadata.get("file_path", "")

                file_chunks.append({
                    "content": content,
                    "metadata": metadata,
                    "score": 0.0,
                    "type": get_folder_type(path)
                })

            print(f"[INFO] Returning {len(file_chunks)} chunks for {filename}")
            return file_chunks

        else:
            print(f"[WARNING] No chunks found for {filename}, falling back to semantic search")
    # ──────────────────────────────────────────────────────
    # OVERVIEW MODE — README only, no vector search
    # ──────────────────────────────────────────────────────
    if mode == "overview":
        print("[INFO] Overview mode — README + semantic merge")

        readme_chunks = get_best_readme_chunk(repo_id)

        vector_store = get_vector_store(repo_id)
        search_query = expand_query(query)
        print(f"[INFO] Expanded query: {search_query}")

        results = vector_store.similarity_search_with_score(search_query, k=15)
        processed = []
        seen = set()

        for doc, score in results:
            file_path = doc.metadata.get("file_path", "")
            key = (file_path, doc.page_content[:100])

            # README boost
            if "readme" in file_path:
                score -= 0.08

            # very light docs penalty
            if "docs" in file_path:
                score += 0.02
            if "docs_src" in file_path:
                score += 0.12
            if key in seen:
                continue
            seen.add(key)

            processed.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
                "type": get_folder_type(file_path, repo_id)
            })

        processed.sort(key=lambda x: keyword_boost(x, query))
        return readme_chunks + processed
    # ──────────────────────────────────────────────────────
# NORMAL MODE — semantic + controlled retrieval
# ──────────────────────────────────────────────────────

    vector_store = get_vector_store(repo_id)

    print(f"[INFO] Searching for: {query}")

    t1 = time.time()
    results = vector_store.similarity_search_with_score(query, k=15)
    t2 = time.time()
    print(f"[TIME] Chroma search only: {t2 - t1:.2f}s")

    seen = set()
    file_counter = {}

    backend_chunks = []
    frontend_chunks = []
    other_chunks = []
    # ─── Step 1: Process all results ───────────────────────
    for doc, score in results:
        file_path = doc.metadata.get("file_path", "").lower()
        file_name = Path(file_path).name 
        # README boost
        if "readme" in file_path:
            score -= 0.08

        # very light docs penalty
        if "docs" in file_path:
            score += 0.02
        if "docs_src" in file_path:
            score += 0.12
        if file_name in NOISE_FILES:
            score += 0.05   
        # limit chunks per file
        chunk = {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": score,
            "type": get_folder_type(file_path, repo_id)
        }
        
        key = (file_path, doc.page_content[:100])
        if key in seen:
            continue
        seen.add(key)

        if file_counter.get(file_path, 0) >= 2:
            continue

        file_counter[file_path] = file_counter.get(file_path, 0) + 1
        
        # split by folder
       # ✅ Use chunk["type"] which already has the corrected classification
        chunk_type = chunk["type"]
        if chunk_type == "backend":
            backend_chunks.append(chunk)
        elif chunk_type == "frontend":
            frontend_chunks.append(chunk)
        else:
            other_chunks.append(chunk)

    # ─── Step 2: Sort each group (with keyword boost) ─────
    backend_chunks.sort(key=lambda x: keyword_boost(x, query))
    frontend_chunks.sort(key=lambda x: keyword_boost(x, query))
    other_chunks.sort(key=lambda x: keyword_boost(x, query))

    # ─── Step 3: Balanced selection ───────────────────────
    final_chunks = []

    has_structure = bool(backend_chunks or frontend_chunks)

    if has_structure:
        # Structured repo (has frontend/backend folders)
        # Balance between layers
        final_chunks += backend_chunks[:3]
        final_chunks += frontend_chunks[:3]
        final_chunks += other_chunks[:2]

        # If one layer is missing, give more slots to the other
        if not backend_chunks:
            final_chunks = frontend_chunks[:5] + other_chunks[:3]
        elif not frontend_chunks:
            final_chunks = backend_chunks[:5] + other_chunks[:3]
    else:
        # Flat repo (library, tool, no frontend/backend)
        # Don't balance by layer — just use score order
        all_chunks = other_chunks   # everything landed here
        all_chunks.sort(key=lambda x: keyword_boost(x, query))
        final_chunks = all_chunks[:k]

    # Safety fallback

    if not final_chunks:
        print("[WARNING] Using raw top-k fallback")

        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
                "type": get_folder_type(doc.metadata.get("file_path", ""), repo_id)
            }
            for doc, score in results[:k]
        ]

    return final_chunks[:k]