from typing import List, Dict
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from functools import lru_cache 
from config import EMBEDDING_MODEL, CHROMA_DIR
import os
from pathlib import Path
# ──────────────────────────────────────────────────────────
# LOAD EMBEDDING MODEL
# ──────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_embedding_model():
    print("[INFO] Loading embedding model...")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

# ──────────────────────────────────────────────────────────
# CREATE / LOAD VECTOR STORE
# ──────────────────────────────────────────────────────────

def get_vector_store(repo_id: str):

    embedding_model = get_embedding_model()
    repo_path = CHROMA_DIR / repo_id

    vector_store = Chroma(
        persist_directory=str(repo_path),
        embedding_function=embedding_model
    )

    return vector_store


# ──────────────────────────────────────────────────────────
# STORE CHUNKS
# ──────────────────────────────────────────────────────────

def store_chunks(chunks: List[Dict], repo_id: str):

    repo_path = CHROMA_DIR / repo_id

    if repo_path.exists() and os.listdir(repo_path):
        print(f"[INFO] Embeddings already exist for repo {repo_id}, skipping...")
        return

    if not chunks:
        print("[WARNING] No chunks to store")
        return

    vector_store = get_vector_store(repo_id)

    texts = []
    metadatas = []

    for chunk in chunks:
        texts.append(chunk["content"])
        metadatas.append({
            "file_path": chunk["file_path"],
            "file_name": Path(chunk["file_path"]).name.lower(),
            "repo_id": repo_id
        })

    print(f"[INFO] Storing {len(texts)} chunks in vector DB...")

    BATCH_SIZE = 100
    
    for i in range(0, len(texts), BATCH_SIZE):
        print(f"[INFO] Processing batch {i//BATCH_SIZE + 1} / {len(texts)//BATCH_SIZE + 1}")

        vector_store.add_texts(
            texts=texts[i:i+BATCH_SIZE],
            metadatas=metadatas[i:i+BATCH_SIZE]
        )


    print("[SUCCESS] Chunks stored successfully")