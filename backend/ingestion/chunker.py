from pathlib import Path
from typing import List, Dict

from config import CHUNK_SIZE, CHUNK_OVERLAP
import re
import uuid

def get_folder_type(file_path: Path) -> str:
    path = str(file_path).lower()

    if "frontend" in path:
        return "frontend"
    elif "backend" in path:
        return "backend"
    else:
        return "other"

def read_file(file_path: Path) -> str:
    """
    Safely read file content.
    """
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


# ──────────────────────────────────────────────────────────
# BASIC FUNCTION / CLASS SPLITTER (heuristic)
# ──────────────────────────────────────────────────────────

def split_by_functions(content: str) -> List[str]:
    """
    Smarter heuristic chunking:
    - Python: def, class
    - JS: function, arrow functions
    - React: hooks, JSX return blocks
    """

    lines = content.split("\n")
    chunks = []
    current_chunk = []

    def is_new_block(line: str) -> bool:
        l = line.strip()

        return (
            # Python
            l.startswith("def ") or
            l.startswith("class ") or

            # JS
            l.startswith("function ") or
            l.startswith("export function") or
            l.startswith("export default") or

            # Arrow functions
            ("=>" in l and "(" in l) or

            # React hooks
            "useEffect(" in l or
            "useState(" in l or

            # JSX return block
            l.startswith("return (")
        )

    for line in lines:
        if is_new_block(line):
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []

        current_chunk.append(line)

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


# ──────────────────────────────────────────────────────────
# FALLBACK CHUNKING (for files without functions)
# ──────────────────────────────────────────────────────────

def chunk_by_size(text: str) -> List[str]:
    """
    Sentence-aware chunking
    """

    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= CHUNK_SIZE:
            current_chunk = f"{current_chunk} {sentence}".strip()
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# ──────────────────────────────────────────────────────────
# MAIN CHUNKING FUNCTION
# ──────────────────────────────────────────────────────────

def chunk_file(file_path: Path) -> List[Dict]:
    # Chunking strategy:
    # - small files → single chunk
    # - large files → function-based split + merge small chunks

    content = read_file(file_path)
    if not content.strip():
        return []

    # ── Helper: build a chunk dict with metadata ──────────
    # Defined here so it can access file_path, folder_type, language
    # without passing them as arguments every time
    def make_chunk(text: str) -> Dict:
        return {
            "content": text,
            "file_path": str(file_path),
        }

    # ── Small file → single chunk, no splitting ───────────
    # 2000 chars ≈ 60 lines of code
    # Keeping it whole means LLM sees full context (imports + logic together)
    if len(content) <= 3000:
        return [make_chunk(content)]

    # ── Large file → split by function/class boundaries ───
    MIN_CHUNK_LINES = 8   # chunks smaller than this get merged

    raw_chunks = split_by_functions(content)

    # Merge tiny chunks into the next one
    merged = []
    buffer = ""

    for chunk in raw_chunks:
        line_count = len(chunk.strip().splitlines())

        if line_count < MIN_CHUNK_LINES:
            # Too small — hold in buffer, prepend to next chunk
            buffer += "\n" + chunk
        else:
            if buffer:
                # Flush buffer into this chunk
                chunk = buffer + "\n" + chunk
                buffer = ""
            merged.append(chunk)

    # Edge case: buffer has content but no more chunks came after it
    if buffer:
        if merged:
            merged[-1] += "\n" + buffer   # attach to last chunk
        else:
            merged.append(buffer)         # it's the only chunk

    # ── Fallback: size-based splitting ────────────────────
    # Triggers when split_by_functions found no boundaries
    # (e.g. a config file, SQL file, or plain markdown)
    if len(merged) <= 1:
        merged = chunk_by_size(content)

    # ── Build final chunk list ────────────────────────────
    return [make_chunk(c) for c in merged if c.strip()]


# ──────────────────────────────────────────────────────────
# PROCESS MULTIPLE FILES
# ──────────────────────────────────────────────────────────

def chunk_files(file_paths: List[Path]) -> List[Dict]:
    """
    Chunk all files and return combined list.
    """

    all_chunks = []

    for file_path in file_paths:
        file_chunks = chunk_file(file_path)
        all_chunks.extend(file_chunks)

    print(f"[INFO] Total chunks created: {len(all_chunks)}")
    return all_chunks