# 8–10. Design decisions, challenges, and setup

← [Structure](04-project-structure-and-data-flows.md) · [Index](../CORTEX_GUIDEBOOK.md) · Next: [Interview Q&A →](06-interview-qa.md)

---

## 8. Key design decisions and trade-offs

### Why hybrid retrieval (FAISS + BM25 + RRF)?

Vectors catch paraphrase (“pillars of OOP” ≈ “four major foundations”). BM25 catches exact tokens (“SRP”, error codes, API names). RRF merges ranks without needing calibrated score scales. Cortex exposes all four modes on `/search` so you can *measure* the lift (`eval/run_eval.py`).

**Trade-off:** More moving parts and latency than “embed + top-k” alone.

### Why cross-encoder rerank after fusion?

Bi-encoder (embedding) search is cheap but approximate. A cross-encoder reads query and passage together — usually better precision on a shortlist. Cortex pulls 20 candidates, reranks, keeps 5 (`top_k_candidates` / `top_k_final`).

**Trade-off:** Downloads a local Hugging Face model; first load is slow; CPU-heavy. Pipeline degrades if load fails.

### Why Gemini for both embed and generate?

One API key, one client (`gemini_client.py`), fewer vendors in a student/demo project. Flash-lite generation keeps cost/latency lower than a heavy reasoning model.

**Trade-off:** Vendor lock-in; offline use needs redesign; rate limits need the retry logic you already wrote.

### Why FAISS `IndexFlatIP` instead of a managed vector DB?

Zero network hop, free, perfect for laptop demos and exact search on small corpora. Chunk id = FAISS id keeps consistency simple.

**Trade-off at scale:** Flat indexes scan all vectors (O(n)). No built-in replication. Multi-process / multi-host sharing of one FAISS file is unsafe without redesign. Alternatives: IVF/HNSW indexes, pgvector, Pinecone, Qdrant.

### Why SQLite?

One file under `backend/storage/app.db`. Compose volume mounts `./backend/storage`. Fine for single-node.

**Trade-off:** Concurrent writes, horizontal scaling, and multi-user SaaS want Postgres (or similar).

### Why LangGraph for four linear steps?

Could be four function calls. LangGraph makes stages explicit in `pipeline.py`, keeps state typed (`PipelineState`), and leaves room for branches later (e.g. “if not grounded, retrieve again”) — **those branches are not implemented today**.

### Why embed *before* the DB transaction?

Embedding is slow and can fail (429). Holding a DB transaction open across that is bad. Code path: embed → then short transaction → add to FAISS → commit; on commit failure, `vector_store.remove` undoes FAISS (`background.py`).

### Why content-hash dedupe?

Same bytes → same SHA-256 → 409 instead of duplicate vectors/chunks. Does **not** detect “same text, different PDF encoding” if bytes differ.

### Why a second LLM groundedness check?

Generation prompts can be ignored. An independent YES/NO audit surfaces `is_grounded` to the UI. It is not a mathematical proof — another LLM can be wrong too.

### Why in-memory response cache with version bump?

Repeated identical questions within TTL skip Gemini cost. Bumping version on ingest/delete means old keys never match — no need to surgically delete entries.

**Trade-off:** Cache dies on process restart; not shared across replicas.

### What I would change at scale (interview-ready list)

Say this in interviews as “what I’d do next,” not as “what the repo already does”:

1. Postgres + proper job queue (Celery/RQ/Arq) instead of FastAPI `BackgroundTasks`  
2. Managed or IVF/HNSW vector index; separate indexing workers  
3. AuthN/AuthZ, per-user document isolation, rate limits  
4. Streaming tokens to the UI  
5. Better eval (LLM-as-judge, citation precision, chunk-level relevance labels)  
6. Multi-turn conversational context (today history is Streamlit-only)  
7. Observability to a real APM (today: per-request `Tracer` dict only)

---

## 9. Challenges, limitations, and improvements

### Gaps & honest limitations (from the code, not guesses)

Call these out yourself before an interviewer finds them:

| Gap | Evidence |
|---|---|
| **No authentication / authorization** | No auth middleware or API keys on routes |
| **No automated unit/integration test suite** | No `tests/` directory in the repo |
| **`eval/requirements.txt` missing** | README mentions it; only `run_eval.py` + JSON exist |
| **README name drift** | README folder name `doc-intel-platform/`, compose file referred to as `.yml` but repo has `docker-compose.yaml` |
| **`cache_ttl_seconds` setting unused** | `ResponseCache()` not passed `settings.cache_ttl_seconds` |
| **No multi-turn RAG memory** | `history` only in Streamlit session state |
| **No streaming responses** | Single blocking `/query` |
| **Groundedness is a fragile YES/NO parse** | `startswith("Y")` — not citation verification |
| **Eval accuracy is phrase containment** | Proxy metric; script itself warns to read answers |
| **BackgroundTasks are process-local** | Restart fails orphan jobs (`session._fail_orphaned_jobs`); no distributed workers |
| **Single-node storage assumptions** | SQLite + local FAISS file + in-memory BM25/cache |
| **Devcontainer starts Streamlit only** | `.devcontainer/devcontainer.json` does not fully mirror Docker Compose backend setup |
| **No OCR** | Image-only PDFs → “No readable text found” |
| **No dedicated FAISS rebuild script** | Reconcile removes strays / warns on missing; re-upload is the recovery path |
| **Embedding dim not documented in config** | Implicit from API response |

### Performance / latency

- Dominant costs: Gemini embed (ingest + query), generate, groundedness (second generate), local cross-encoder on CPU.  
- `Tracer` exposes stage ms — use that in demos.  
- Cache helps repeated questions only.

### Cost

- Every ingest embeds all chunks (batches of 50).  
- Every uncached query: rewrite + query embed + answer + groundedness ≈ **multiple** Gemini calls.  
- Reranker is local (no API $) but needs model download + RAM/CPU.

### Accuracy / hallucination

**Helps:** hybrid retrieve, rerank, strict prompt, citations, groundedness flag, “I don’t know” empty-retrieval path.  
**Still can fail:** wrong chunks retrieved; model cites poorly; YES/NO judge errs; phrase-eval false positives/negatives.

### Security

- Anyone with network access to `:8000` can upload/delete/query.  
- Uploaded files land on disk under `storage/uploads/`.  
- API key in `.env` (gitignored).  
- No virus scanning, no per-user quotas beyond max upload size.

### Scaling

- Vertical: larger machine helps FAISS flat + cross-encoder.  
- Horizontal: need shared DB, shared/replicated vector index, sticky or external cache, real queue — **not in repo**.

### Evaluation (what exists)

- Retrieval Recall@5 at **document filename** level (not chunk-level labels).  
- E2E: substring match + grounded rate + latency.  
- Dataset assumes `oops_demo.pdf` content.

---

## 10. Setup and run

### Prerequisites

- Docker **or** Python 3.12-ish locally  
- Gemini API key from Google AI Studio  

### Env variables

From `.env.example` + `Settings` in `config.py`:

| Variable / setting | Required? | Default | Meaning |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | — | Auth for Gemini |
| `GEMINI_GENERATION_MODEL` | No | `gemini-3.1-flash-lite` | Answer / rewrite / groundedness model |
| `GEMINI_EMBEDDING_MODEL` | No | `gemini-embedding-2` | Embedding model |
| `reranker_model` | Code default only | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Not in `.env.example` but overridable via env if pydantic-settings picks it up (`RERANKER_MODEL`) |
| `DATA_DIR` | No | `backend/storage` | DB, uploads, index |
| `MAX_UPLOAD_MB` | No | `25` | Upload cap |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | No | `900` / `150` | Chunking |
| `TOP_K_CANDIDATES` / `TOP_K_FINAL` | No | `20` / `5` | Retrieval depths |
| `CACHE_TTL_SECONDS` | No | `600` | Intended cache TTL (see gap above) |
| `BACKEND_URL` (frontend) | No | `http://localhost:8000` | Where Streamlit posts |

Copy:

```bash
cp .env.example .env
# edit GEMINI_API_KEY=...
```

### Option A — Docker Compose (recommended)

```bash
docker compose up --build
```

- UI: http://localhost:8501  
- API docs: http://localhost:8000/docs  
- Healthcheck hits `/health`  
- Volume: `./backend/storage` persists DB + FAISS + uploads  

Note: compose file is `docker-compose.yaml` (not `.yml`).

### Option B — Local processes

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# also need CPU torch for sentence-transformers — Docker installs torch explicitly;
# locally you may need: pip install torch (CPU) before/with requirements
uvicorn app.main:app --reload --port 8000

# Frontend (other terminal)
cd frontend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Backend Dockerfile preinstalls `torch==2.7.1` CPU from PyTorch’s index because `sentence-transformers` needs it — local installs should do something similar if the reranker must load.

### Evaluation

```bash
# backend running, documents ingested, dataset filled
cd eval
pip install requests   # no eval/requirements.txt in repo
python run_eval.py
```

### Storage layout after running

```
backend/storage/
  app.db
  uploads/{job_id}.{pdf|txt|md}
  index/faiss.index
```
