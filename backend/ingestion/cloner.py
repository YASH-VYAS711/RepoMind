import hashlib
from pathlib import Path
from git import Repo, GitCommandError

from config import REPOS_DIR

def generate_repo_id(repo_url: str) -> str:
    return hashlib.md5(repo_url.encode()).hexdigest()


def get_repo_path(repo_id: str) -> Path:
    return REPOS_DIR / repo_id


def clone_repo(repo_url: str) -> Path:
    if not repo_url.startswith("http"):
        raise ValueError("Invalid repository URL")
    repo_id = generate_repo_id(repo_url)

    repo_path = get_repo_path(repo_id)

    if repo_path.exists() and any(repo_path.iterdir()):
        print(f"[INFO] Repo already exists: {repo_path}")
        return repo_path

    try:
        print(f"[INFO] Cloning repo: {repo_url}")
        Repo.clone_from(repo_url, repo_path)

        print(f"[SUCCESS] Repo cloned to: {repo_path}")
        return repo_path

    except GitCommandError as e:
        raise Exception(f"Git clone failed: {e.stderr}")