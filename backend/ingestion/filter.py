from pathlib import Path
from typing import List
from config import ALLOWED_EXTENSIONS, IGNORED_DIRS, IGNORED_FILES, MAX_FILE_SIZE

MAX_FILES = 400

# Special filenames without extensions
SPECIAL_FILENAMES = {"Dockerfile", "Makefile", "README"}


def is_valid_file(file_path: Path) -> bool:
    """
    Check if a file should be included for processing.
    """    
    # Skip hidden folders except important files
    for part in file_path.parts:
        if part.startswith(".") and part not in {".env", ".env.example"}:
            return False

    # Skip if not a file
    if not file_path.is_file():
        return False

    # Skip ignored filenames
    if file_path.name in IGNORED_FILES:
        return False

    # Skip large files
    if file_path.stat().st_size > MAX_FILE_SIZE:
        return False

    # Check extension
    if not (
        file_path.suffix.lower() in ALLOWED_EXTENSIONS
        or file_path.name in SPECIAL_FILENAMES
    ):
        return False

    return True

def get_valid_files(repo_path: Path) -> List[Path]:
    all_files = []
    
    for path in repo_path.rglob("*"):
        if any(part.lower() in IGNORED_DIRS for part in path.parts):
            continue
        if is_valid_file(path):
            all_files.append(path)

    # ── Sort: source code first, docs last ──────────────
    def priority(p: Path) -> int:
        s = str(p).lower().replace("\\", "/")
        if "/docs_src/" in s:   return 3   # tutorial snippets — lowest priority
        if "/docs/" in s:       return 2   # documentation
        if "/test/" in s or "/tests/" in s:
            return 1   # tests
        return 0                           # actual source — highest priority

    all_files.sort(key=priority)

    # Apply cap AFTER sorting so source files are never cut off
    if len(all_files) > MAX_FILES:
        print(f"[INFO] Capping {len(all_files)} files to {MAX_FILES}")

    print(f"[INFO] Total valid files: {min(len(all_files), MAX_FILES)}")
    return all_files[:MAX_FILES]