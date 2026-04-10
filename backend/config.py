# backend/config.py

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ── Paths ──────────────────────────────────────────────────
# BASE_DIR is the backend/ folder
BASE_DIR = Path(__file__).resolve().parent

if os.getenv("HF_TOKEN"):
    os.environ["HUGGINGFACE_HUB_TOKEN"] = os.getenv("HF_TOKEN")
# Where cloned repos will be temporarily stored
REPOS_DIR = BASE_DIR / "cloned_repos"

# Where ChromaDB will persist its data
CHROMA_DIR = BASE_DIR / "chroma_db"

# Create these directories if they don't exist yet
REPOS_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

# ── Embedding model ────────────────────────────────────────

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en")

# ── LLM (via Ollama) ───────────────────────────────────────
# Ollama runs as a local server on port 11434 by default


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")

# ── Retrieval settings ─────────────────────────────────────
# How many chunks to retrieve per query
# k=5 is a good starting point — we'll tune this later
TOP_K = int(os.getenv("TOP_K", 5))

# ── Chunking settings ──────────────────────────────────────
# Max characters per chunk
# Smaller = more precise retrieval, Larger = more context per chunk
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 2500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 150))
  # Characters shared between adjacent chunks
                     # Overlap prevents cutting a function in half
MAX_FILE_SIZE = 500_000
# ── File filtering ─────────────────────────────────────────
# File extensions we want to index
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".go", ".rs", ".cpp", ".c",
    ".cs", ".rb", ".php", ".swift",
    ".md", ".yml", ".yaml", ".json", ".env.example",
    ".toml", ".cfg", ".ini", ".sh", ".txt", ".dockerfile", ".env",
    ".sql", ".proto", ".graphql"
}

# Folders to completely skip during ingestion
IGNORED_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "target", "vendor",
    ".idea", ".vscode", "coverage", ".pytest_cache"
}

# Files to completely skip
IGNORED_FILES = {
    "package-lock.json", "yarn.lock", "poetry.lock",
    "Pipfile.lock", ".DS_Store", "*.pyc", "*.pyo"
}