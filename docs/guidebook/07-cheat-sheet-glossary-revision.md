# 12–14. Cheat sheet, glossary, last-minute revision

← [Q&A](06-interview-qa.md) · [Index](../CORTEX_GUIDEBOOK.md) · Next: [Self-test →](08-self-test.md)

---

## 12. “If they ask me X, I say Y” cheat sheet

| If they ask… | You say… |
|---|---|
| What is Cortex? | Grounded hybrid RAG Q&A over my PDFs/TXT/MD with citations. |
| Why not just ChatGPT? | Private docs, citations, and an explicit “don’t invent” loop with retrieval. |
| What’s hybrid search? | FAISS semantic + BM25 keyword, fused with RRF, then optional cross-encoder. |
| What’s your vector DB? | FAISS `IndexFlatIP` on disk; SQLite is source of truth for text. |
| Similarity metric? | Cosine via L2-normalized inner product. |
| Chunk size? | 900 chars, 150 overlap, boundary-aware cuts. |
| Embedding model? | Gemini `gemini-embedding-2` (configurable). |
| LLM? | Gemini `gemini-3.1-flash-lite` for rewrite/answer/judge. |
| Reranker? | `cross-encoder/ms-marco-MiniLM-L-6-v2` via sentence-transformers. |
| Orchestration? | LangGraph: rewrite → retrieve → generate → groundedness. |
| How do you stop hallucinations? | Strict context prompt, citations, empty-retrieval refusal, second-pass YES/NO check. |
| How do you know retrieval works? | `/search` modes + `eval/run_eval.py` Recall@5 comparison. |
| Consistency trick? | Chunk DB id == FAISS id; embed before commit; rollback vectors on failed commit. |
| Async upload? | 202 + job polling; FastAPI BackgroundTasks. |
| Cache invalidation? | Version integer baked into cache keys; bump on ingest/delete. |
| Auth? | None yet — known gap. |
| Scale limit? | Single-node SQLite + flat FAISS + in-memory BM25/cache. |
| Frontend? | Streamlit calling the FastAPI backend. |
| Duplicate files? | SHA-256 content hash → HTTP 409. |
| Reranker down? | Query path degrades to hybrid; search path returns 503. |
| Multi-turn chat? | UI history only; backend is stateless per question. |
| Where’s the config? | `backend/app/config.py` + root `.env`. |
| Biggest next step? | Auth + durable job queue + stronger eval. |

---

## 13. Glossary (simple words)

| Term | Plain meaning |
|---|---|
| **RAG** | Look up relevant text, then ask the LLM to answer using it. |
| **LLM** | Large language model — the text-generating AI (here, Gemini). |
| **Hallucination** | Fluent answer that isn’t supported by the evidence. |
| **Embedding** | Text turned into a list of numbers capturing meaning. |
| **Vector** | That list of numbers. |
| **Dimension** | How long the vector is (Cortex takes whatever Gemini returns). |
| **Cosine similarity** | “How same-direction are two vectors?” after normalizing length. |
| **FAISS** | Facebook library for fast vector search. |
| **IndexFlatIP** | Exact FAISS index using inner product scores. |
| **BM25** | Classic keyword ranking (like a smart TF-IDF). |
| **Hybrid search** | Combining vector + keyword results. |
| **RRF (Reciprocal Rank Fusion)** | Merge rankings with `1/(k+rank)` scores. |
| **Top-k** | Keep the best *k* results. |
| **Candidate set** | Larger shortlist (here 20) before final top-k (5). |
| **Reranker / cross-encoder** | Model that scores query+passage together and reorders. |
| **Bi-encoder** | Separately embed query and docs (FAISS path). |
| **Chunk** | A small slice of a document stored and searched as a unit. |
| **Overlap** | Shared text between neighboring chunks. |
| **Ingestion** | Upload → parse → chunk → embed → store. |
| **Retrieval** | Finding the best chunks for a question. |
| **Prompt** | The full instruction + context string sent to the LLM. |
| **Citation** | Pointer back to a source chunk/file shown to the user. |
| **Groundedness** | Whether the answer sticks to retrieved facts. |
| **LangGraph** | Library to define LLM pipelines as graphs of steps. |
| **FastAPI** | Python web framework for the API. |
| **Uvicorn** | ASGI server that runs FastAPI. |
| **Streamlit** | Python toolkit for the chat UI. |
| **SQLModel** | ORM combining SQLAlchemy + Pydantic models. |
| **SQLite** | File-based SQL database. |
| **Background task** | Work continued after the HTTP response is sent. |
| **TTL** | Time-to-live — how long a cache entry stays valid. |
| **Idempotency / dedupe** | Don’t process the same content twice (hash check). |
| **Backoff** | Wait longer between retries after failures. |
| **Jitter** | Extra random delay so retries don’t sync-stampede. |
| **Recall@k** | Did the right item appear in the top *k* results? |
| **Latency** | How long a request takes. |
| **Source of truth** | The system you trust if copies disagree (here, SQLite text). |
| **Derived index** | Rebuildable structure (FAISS) computed from the source of truth. |
| **Degraded mode** | System still answers after skipping a broken optimization (reranker). |
| **OCR** | Reading text from images (not in Cortex). |
| **Token** | Pieces of text models count/bill by; also “word-like” units in BM25. |
| **Stopwords** | Common words (“the”, “and”) dropped in keyword search. |
| **Pydantic** | Data validation library for request/response models. |
| **OpenAPI / `/docs`** | Interactive API documentation FastAPI generates. |
| **Compose healthcheck** | Docker probe ensuring backend `/health` is OK before starting UI. |

---

## 14. Last-minute revision page

**One-page brain dump — read out loud the night before.**

**Cortex** = grounded Q&A over *my* PDF/TXT/MD.  
**Stack** = FastAPI + Streamlit + SQLite + FAISS + BM25 + CrossEncoder + Gemini + LangGraph + Docker Compose.

**Ingest:** `/ingest` → hash dedupe → Job → background: parse (pypdf cleanup) → chunk 900/150 → embed Gemini batches of 50 → create Document/Chunks → FAISS add with chunk ids → invalidate BM25 + bump cache → job complete.  
**Query:** cache? → rewrite → FAISS+BM25 → RRF → rerank (or degrade) → top 5 → answer with `[Source N]` → YES/NO groundedness → trace ms.

**Defaults:** candidates 20, final 5, cache ~10 min, upload ≤25 MB, models flash-lite + embedding-2 + ms-marco MiniLM.

**Pride points:** hybrid+measurable; chunk id = vector id; embed-before-commit; graceful rerank failure; cache versioning; citations + grounded flag.

**Honest gaps:** no auth, no real test suite, no durable queue, no multi-turn memory, SQLite/FAISS single-node, groundedness is another LLM, eval is phrase/doc proxies.

**⭐ Files:** `graph/nodes.py`, `retrieval/hybrid.py`, `ingestion/background.py`, `retrieval/vector_store.py`, `api/query.py`, `config.py`.

**Spoken closer:**  
> “It’s a small system, but I designed it so I can *measure* retrieval, keep text and vectors consistent, and surface when an answer may not be grounded — instead of only demoing a happy-path chatbot.”
