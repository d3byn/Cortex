from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.session import init_db

@asynccontextmanager
async def lifespan(app: FastAPI): #manages the application's lifespan events (startup and shutdown)
    init_db()
    yield #separate the startup and shutdown events

app = FastAPI(
    title="Cortex - Document Intelligence & Retrieval Platform",
    description="A grounded, citation-backed RAG API powered by Gemini.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    return {"status": "ok"}