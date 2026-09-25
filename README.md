# Cortex - A Document Intelligence & Retrieval Platform

A grounded, citation-backed question-answering system over your own PDF, TXT
and Markdown files — built on FastAPI, Gemini, FAISS, BM25, a cross-encoder
reranker, and a LangGraph pipeline, with a Streamlit chat frontend.

Ask a question, and the system finds the exact passages that answer it,
cites them by source, and honestly says "I don't know" when your documents
don't contain the answer — instead of making something up.

## Why this project

Most RAG demos wire an embedding model to a vector database and call it
done. This one is built around a harder, more honest question: **how do you
know it's actually working, and how do you keep it working as data changes?**
That shows up in a few deliberate choices:

- **Hybrid retrieval, not just vectors.** Semantic (FAISS) and keyword
  (BM25) search are fused with Reciprocal Rank Fusion, then reordered by a
  cross-encoder. An evaluation run (`eval/run_eval.py`) measures the actual
  lift this gives over vector search alone — see [Evaluation](#evaluation).
- **Grounding is checked, not assumed.** Every answer is generated strictly
  from retrieved context with inline citations, then audited by a second,
  independent LLM call that flags unsupported claims.
- **Consistency is designed in, not patched on.** A chunk's database ID
  doubles as its FAISS ID, so vectors and text can never drift apart the way
  they would with a separate mapping table. Ingestion embeds *before*
  opening a database transaction, so a failure anywhere leaves either
  everything saved or nothing — never a half-saved document.
- **Failures are handled on purpose, not by accident.** Retryable API
  errors (rate limits, transient 5xx) are retried with backoff. A missing
  reranker degrades the pipeline one step (skips only that optimization)
  rather than failing the whole answer. A response cache is invalidated the
  moment the underlying documents change, so a stale answer is never served
  after new data arrives.

## Architecture

```
INGESTION (once per file)
  upload -> parse (PDF/TXT/MD) -> chunk (~900 chars, overlapping)
          -> embed (Gemini) -> save (SQLite text + FAISS vectors, atomically)

QUERY (every question)
  question -> rewrite (standalone search query)
           -> hybrid retrieve (FAISS + BM25 -> Reciprocal Rank Fusion -> cross-encoder rerank)
           -> generate answer (Gemini, grounded in retrieved chunks, cited)
           -> check groundedness (a second, independent LLM audit)
```

Storage: SQLite holds the source of truth (documents, chunks, upload jobs).
FAISS holds one vector per chunk, keyed by the chunk's own database ID — a
derived index that can always be rebuilt from SQLite, never the reverse.

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + Uvicorn |
| Database | SQLite via SQLModel |
| Embeddings & generation | Google Gemini (`gemini-embedding-2`, `gemini-3.1-flash-lite`) |
| Vector search | FAISS (`IndexFlatIP`, cosine similarity) |
| Keyword search | BM25 (`rank_bm25`) |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Orchestration | LangGraph |
| Frontend | Streamlit |
| Containers | Docker Compose |

## Getting started

### Option A: Docker (recommended)

```bash
git clone <your-repo-url>
cd doc-intel-platform
cp .env.example .env        # add your Gemini API key
docker compose up --build
```

Frontend: http://localhost:8501 · Backend docs: http://localhost:8000/docs

### Option B: Run locally

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # add your Gemini API key
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Get a Gemini API key at https://aistudio.google.com/apikey.

## Evaluation

Fill in `eval/eval_dataset.json` with real questions about your own
documents, then, with the backend running:

```bash
cd eval
pip install -r requirements.txt
python run_eval.py
```

This reports Recall@5 for each of four retrieval modes (vector, keyword,
hybrid, hybrid + rerank), plus end-to-end accuracy, groundedness rate, and
per-stage latency for the full pipeline. My own run over N real questions:

```
<PASTE YOUR OWN run_eval.py OUTPUT HERE>
```

## API reference

Full interactive docs at `/docs` once the backend is running. Key endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /ingest` | Upload a file; returns a job id to poll |
| `GET /jobs/{id}` | Ingestion progress |
| `GET /documents` / `DELETE /documents/{id}` | List / remove documents |
| `POST /search` | Retrieval only, with a `mode` to compare strategies |
| `POST /query` | Full pipeline: rewrite, retrieve, answer, cite, ground |

## Known limitations

- **No OCR.** Scanned PDFs (images of text) have no extractable text and
  will be rejected at ingestion with a clear error.
- **Background jobs don't survive a server restart.** An in-progress
  upload is marked "failed" if the server restarts mid-job (self-healing
  on startup, but the file must be re-uploaded). A production system would
  use a durable task queue (e.g. Celery + Redis) instead of FastAPI's
  built-in background tasks.
- **Single-process only.** The response cache and BM25 index live in
  process memory, so they're not shared across multiple backend instances.
  SQLite itself only supports one writer at a time. Both are fine at
  personal/demo scale; a multi-instance deployment would need a shared
  cache (Redis) and a server database (Postgres).
- **No relevance threshold.** Retrieval always returns its best-available
  candidates, even for an off-topic question — nearest-neighbor search
  has no natural "found nothing" signal. The system relies on the LLM's
  prompt instructions and the groundedness check to catch this, rather
  than an empty result list.

## Project structure

```
doc-intel-platform/
├── backend/
│   └── app/
│       ├── api/          # FastAPI routers (ingest, documents, search, query)
│       ├── ingestion/     # parsing, chunking, background processing
│       ├── retrieval/     # embeddings, FAISS, BM25, fusion, reranking
│       ├── graph/         # LangGraph pipeline (nodes, state, wiring)
│       ├── cache/         # response cache
│       ├── db/            # SQLModel models + session
│       └── config.py, main.py, gemini_client.py, schemas/
├── frontend/
│   └── app.py             # Streamlit UI
├── eval/
│   ├── eval_dataset.json
│   └── run_eval.py
└── docker-compose.yml
```