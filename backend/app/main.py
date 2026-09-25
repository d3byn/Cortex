import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import Session, select
from app.api import documents, ingest, search
from app.db.models import Chunk
from app.db.session import engine, init_db
from app.retrieval.vector_store import vector_store
from app.retrieval.reranker import reranker
from app.api import documents, ingest, query, search

logger = logging.getLogger("uvicorn.error")

def _check_index_consistency() -> None:
    with Session(engine) as session:
        chunk_ids = set(session.exec(select(Chunk.id)).all())
    strays, missing = vector_store.reconcile(chunk_ids)
    logger.info("Index check: %d chunks, %d vectors, %d stray vectors removed",
                len(chunk_ids), vector_store.count, strays)
    if missing:
        logger.warning("%d chunks have no vector and cannot be found by meaning. "
                       "Delete and re-upload the affected documents.", missing)

@asynccontextmanager
async def lifespan(app: FastAPI): #manages the application's lifespan events (startup and shutdown)
    init_db()
    _check_index_consistency()
    threading.Thread(target=reranker.warm_up, daemon=True).start()   # load model without blocking startup
    yield #separate the startup and shutdown events

app = FastAPI(
    title="Cortex - Document Intelligence & Retrieval Platform",
    description="A grounded, citation-backed RAG API powered by Gemini.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(ingest.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(query.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}