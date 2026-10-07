# Cortex Interview Guidebook

**Audience:** you (Debayan), preparing for backend / AI engineering interviews  
**Repo:** this Cortex project — grounded Q&A over your own PDF / TXT / Markdown files  
**How to use:** start here, then read the numbered chapters in order. Before an interview, skim the [last-minute revision page](guidebook/07-cheat-sheet-glossary-revision.md#14-last-minute-revision-page).

---

## Coverage checklist (re-scanned against the repo)

Every item below was verified against real files in this repository before writing. Nothing important from the tree was skipped on purpose.

| Covered? | Area | Primary files |
|:---:|---|---|
| ✅ | Pitch, problem, users | `README.md` |
| ✅ | FastAPI app lifespan, routers, health | `backend/app/main.py` |
| ✅ | Settings / env / paths | `backend/app/config.py`, `.env.example` |
| ✅ | Ingest API (upload, hash, jobs) | `backend/app/api/ingest.py` |
| ✅ | Documents list/delete | `backend/app/api/documents.py` |
| ✅ | Search-only API + modes | `backend/app/api/search.py` |
| ✅ | Full query API + cache | `backend/app/api/query.py` |
| ✅ | PDF/TXT/MD parsing + PDF cleanup | `backend/app/ingestion/parsers.py` |
| ✅ | Chunking (size, overlap, boundaries) | `backend/app/ingestion/chunker.py` |
| ✅ | Background ingest + atomic save | `backend/app/ingestion/background.py` |
| ✅ | Gemini embeddings + retries | `backend/app/retrieval/embeddings.py` |
| ✅ | FAISS vector store (IndexFlatIP, IDs) | `backend/app/retrieval/vector_store.py` |
| ✅ | BM25 keyword store | `backend/app/retrieval/keyword_store.py` |
| ✅ | Reciprocal Rank Fusion | `backend/app/retrieval/fusion.py` |
| ✅ | Hybrid retrieve orchestration | `backend/app/retrieval/hybrid.py` |
| ✅ | Cross-encoder reranker | `backend/app/retrieval/reranker.py` |
| ✅ | Chunk lookup / `RetrievedChunk` | `backend/app/retrieval/lookup.py` |
| ✅ | LangGraph pipeline wiring | `backend/app/graph/pipeline.py`, `state.py`, `nodes.py` |
| ✅ | Prompt build, answer, groundedness | `backend/app/graph/nodes.py` |
| ✅ | Gemini generate client | `backend/app/gemini_client.py` |
| ✅ | SQLite models (Document, Chunk, Job) | `backend/app/db/models.py`, `session.py` |
| ✅ | Response cache + version bump | `backend/app/cache/response_cache.py` |
| ✅ | Per-stage tracing | `backend/app/tracing/tracer.py` |
| ✅ | Pydantic request/response schemas | `backend/app/schemas/models.py` |
| ✅ | Streamlit frontend | `frontend/app.py` |
| ✅ | Eval harness + dataset | `eval/run_eval.py`, `eval_dataset.json` |
| ✅ | Docker / Compose / Dockerfiles | `docker-compose.yaml`, `backend/Dockerfile`, `frontend/Dockerfile` |
| ✅ | Dependencies | `backend/requirements.txt`, `frontend/requirements.txt` |
| ✅ | Devcontainer | `.devcontainer/devcontainer.json` |
| ✅ | Gaps & honest limitations | See [chapter 09](guidebook/05-design-challenges-setup.md#9-challenges-limitations-and-improvements) |
| ✅ | Interview Q&A (40+), cheat sheet, glossary, self-test | Chapters 11–15 |

---

## Chapter index

| # | Chapter | File |
|---|---|---|
| 1–2 | 30-second pitch + 2-minute spoken explanation | [01-pitch-and-overview.md](guidebook/01-pitch-and-overview.md) |
| 3–4 | Architecture, tech stack, RAG explained simply | [02-architecture-and-rag.md](guidebook/02-architecture-and-rag.md) |
| 5 | End-to-end walkthrough (ingest → answer) | [03-end-to-end-walkthrough.md](guidebook/03-end-to-end-walkthrough.md) |
| 6–7 | Project structure + data-flow sequence diagrams | [04-project-structure-and-data-flows.md](guidebook/04-project-structure-and-data-flows.md) |
| 8–10 | Design decisions, challenges, setup & env | [05-design-challenges-setup.md](guidebook/05-design-challenges-setup.md) |
| 11 | Interview Q&A bank (40+ answers) | [06-interview-qa.md](guidebook/06-interview-qa.md) |
| 12–14 | Cheat sheet, glossary, last-minute revision | [07-cheat-sheet-glossary-revision.md](guidebook/07-cheat-sheet-glossary-revision.md) |
| 15 | Self-test (15 questions, answers hidden) | [08-self-test.md](guidebook/08-self-test.md) |

Also: [guidebook/index.md](guidebook/index.md) mirrors this table.

---

## ⭐ The 6 files you must know cold

If you can open these and explain them without notes, you can defend this project in an interview:

1. ⭐ `backend/app/graph/nodes.py` — rewrite → retrieve → answer → groundedness check  
2. ⭐ `backend/app/retrieval/hybrid.py` — vector + BM25 + RRF + optional rerank  
3. ⭐ `backend/app/ingestion/background.py` — embed first, then one atomic DB + FAISS commit  
4. ⭐ `backend/app/retrieval/vector_store.py` — FAISS `IndexFlatIP`, chunk DB id = vector id  
5. ⭐ `backend/app/api/query.py` — cache → LangGraph invoke → citations + trace  
6. ⭐ `backend/app/config.py` — every important knob (chunk size, top-k, models, paths)

---

*Generated from the code as it exists in this repo. Prefer the code over this guide if they ever disagree.*
