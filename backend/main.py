from fastapi import FastAPI
from pydantic import BaseModel
from ingestion.cloner import clone_repo, generate_repo_id
from ingestion.filter import get_valid_files
from ingestion.chunker import chunk_files
from rag.embedder import store_chunks
from rag.llm_pipeline import ask_question
from contextlib import asynccontextmanager
from rag.embedder import get_embedding_model
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi import HTTPException
import shutil
from config import REPOS_DIR, CHROMA_DIR
# ──────────────────────────────────────────────────────────
# REQUEST SCHEMA
# ──────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    repo_id: str

class IngestRequest(BaseModel):
    repo_url: str

def normalize_url(url: str) -> str:
    return url.strip().lower().replace(".git", "").rstrip("/")
# ──────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when server starts
    print("[INFO] Loading embedding model...")
    get_embedding_model()   # loads and caches immediately
    print("[INFO] Embedding model ready")
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all for now (dev only)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def home():
    return {"message": "RepoMind backend running"}


# Replace the entire /query endpoint
@app.post("/query")
def query_repo(request: QueryRequest):
    def stream():
        try:
            for token in ask_question(request.question, request.repo_id):
                yield token
        except Exception as e:
            yield f"ERROR:{str(e)}"

    return StreamingResponse(
        stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no" }
    )


@app.post("/ingest/stream")
def ingest_repo_stream(request: IngestRequest):
    def stream():
        try:
            normalized_url = normalize_url(request.repo_url)
            repo_id = generate_repo_id(normalized_url)
            repo_path = clone_repo(normalized_url)
            yield "Cloning repository...\n"
            yield f"Scanning files...\n"
            files = get_valid_files(repo_path)
            yield f"Found {len(files)} files. Chunking...\n"
            chunks = chunk_files(files)
            yield f"Creating {len(chunks)} chunks. Embedding...\n"
            store_chunks(chunks, repo_id)
            yield f"DONE:{repo_id}\n"  # sentinel for frontend to parse
        except Exception as e:
            yield f"ERROR:{str(e)}\n"
    return StreamingResponse(stream(), media_type="text/plain")


@app.get("/repos/{repo_id}/status")
def repo_status(repo_id: str):
    from rag.retriever import get_vector_store
    vs = get_vector_store(repo_id)

    count = vs._collection.count()
    return {"repo_id": repo_id, "ingested": count > 0, "chunks": count}



@app.delete("/repos/{repo_id}")
def delete_repo(repo_id: str):
    try:
        repo_path = REPOS_DIR / repo_id
        chroma_path = CHROMA_DIR / repo_id

        if repo_path.exists():
            shutil.rmtree(repo_path)

        if chroma_path.exists():
            shutil.rmtree(chroma_path)

        return {"message": f"Repo {repo_id} deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))