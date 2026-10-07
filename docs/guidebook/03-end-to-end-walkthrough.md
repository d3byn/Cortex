# 5. End-to-end walkthrough

← [Architecture](02-architecture-and-rag.md) · [Index](../CORTEX_GUIDEBOOK.md) · Next: [Structure & flows →](04-project-structure-and-data-flows.md)

This chapter follows real code. Open the starred files while you read.

---

## 5.1 Document ingestion (loading, parsing, cleaning)

**Entry:** `POST /ingest` in `backend/app/api/ingest.py`

What happens:

1. **Filename → type** via `detect_file_type` (`parsers.py`): only `pdf`, `txt`, `md` / `markdown`.
2. **Read bytes**; reject empty (400) or over `max_upload_mb` (default 25 MB → 413).
3. **SHA-256 content hash**; if a `Document` with the same hash exists → **409 Conflict** (duplicate).
4. Create a `Job` row (`status=queued`), save file to `storage/uploads/{job_id}.{type}`.
5. Schedule `process_document(...)` as a FastAPI `BackgroundTasks` job; return **202** with `job_id`.

**Parsing** (`backend/app/ingestion/parsers.py`):

| Type | Function | Notes |
|---|---|---|
| PDF | `parse_pdf` | `pypdf.PdfReader`; each page cleaned then joined |
| TXT / MD | `parse_text` | UTF-8 with `errors="replace"` |
| Empty text | `parse_file` raises | “No readable text found…” |

**PDF cleaning heuristics** (real code, not marketing):

- `_rejoin_spaced_glyphs` — fixes “g l y p h   s p a c e d” PDF extraction  
- `_rejoin_word_per_line` — fixes one-word-per-line PDFs with lots of blank padding  
- Non-breaking spaces `\xa0` → normal space  

**Progress polling:** `GET /jobs/{job_id}` returns `JobStatus` (progress, stage, error, document_id).

**Frontend:** `frontend/app.py` → `start_ingestion` + `@st.fragment` `ingestion_progress` polls every 1s.

---

## 5.2 Chunking

**File:** `backend/app/ingestion/chunker.py` · **Called from:** `background.process_document`

| Knob | Default (`config.py`) | Meaning |
|---|---|---|
| `chunk_size` | 900 | Target max characters per chunk |
| `chunk_overlap` | 150 | Characters shared with the next chunk |

**Strategy:**

- Walk the text with a sliding window.
- Prefer cutting at natural boundaries: `\n\n`, `\n`, `. `, `? `, `! `, `; `, `, `, space (`_SEPARATORS` + `_find_cut`).
- Overlap advances `end - overlap`, then snaps forward to a whitespace boundary so you do not start mid-word.
- Rejects `overlap >= chunk_size`.

**Why these numbers (honest):** The README and config choose ~900 / 150 as a practical balance: enough context for an answer, small enough for many chunks in a prompt and for embedding batches. There is **no automated chunk-size sweep in the repo** — treat 900/150 as a chosen default, not a proven optimum from this codebase.

**Why overlap:** A sentence that sits on a boundary still appears fully in at least one chunk, so retrieval does not lose half a thought.

---

## 5.3 Embeddings

**File:** ⭐ `backend/app/retrieval/embeddings.py`  
**Client:** `backend/app/gemini_client.py` (`genai.Client`)

| Detail | What the code does |
|---|---|
| Model | `settings.gemini_embedding_model` (default `gemini-embedding-2`) |
| Batch size | `EMBED_BATCH_SIZE = 50` |
| Document formatting | For embedding-2: `"title: none \| text: {chunk}"` |
| Query formatting | For embedding-2: `"task: question answering \| query: {question}"` |
| Older models | If model name does **not** contain `embedding-2`, uses `EmbedContentConfig(task_type=...)` instead of prefixes |
| Retries | Codes 429/500/502/503/504, up to 5 attempts, exponential backoff + jitter |
| Output | `numpy` float32 array shape `(N, dim)` |

**Dimensions:** Whatever Gemini returns. Cortex never hardcodes `768` or `3072`. FAISS learns `dim` from the first `add`.

**Ingest order (important design):** In `background.process_document`, `embed_texts(pieces)` runs **before** opening the DB transaction that creates `Document` / `Chunk` rows. Slow/failing API work does not hold a half-written document.

---

## 5.4 Vector store / database

### SQLite (source of truth)

**Files:** `backend/app/db/models.py`, `backend/app/db/session.py`  
**Path:** `backend/storage/app.db` (via `settings.db_path`)

| Table | Role |
|---|---|
| `Document` | filename, file_type, content_hash (indexed), num_chunks, created_at |
| `Chunk` | id (PK), document_id FK, chunk_index, text — **this id is also the FAISS id** |
| `Job` | uuid id, status/progress/stage/error, optional document_id |

On startup (`init_db`): create tables; mark any `queued`/`processing` jobs as **failed** (“Server restarted while this file was processing…”).

### FAISS (derived index)

**File:** ⭐ `backend/app/retrieval/vector_store.py`  
**Path:** `backend/storage/index/faiss.index`

| Detail | Implementation |
|---|---|
| Index type | `IndexIDMap(IndexFlatIP(dim))` — exact inner-product search |
| Similarity | Vectors L2-normalized → IP ≈ **cosine similarity** |
| IDs | Chunk primary keys (`add_with_ids`) |
| Persistence | Write `.tmp` then `os.replace` (atomic) |
| Concurrency | `threading.RLock` |
| Upsert | `remove_ids` then `add_with_ids` for the same ids |
| Filter | Optional `IDSelectorBatch` so document scoping happens **before** ranking |
| Startup repair | `main._check_index_consistency` → `reconcile`: drop stray vectors; warn on chunks missing vectors |

**Design slogan from README (matches code):** SQLite is source of truth; FAISS can be rebuilt from chunks — never the reverse. (Rebuild tooling is not a separate script in the repo; reconcile only removes orphans / reports missing.)

### Keyword index (in-memory BM25)

**File:** `backend/app/retrieval/keyword_store.py`

- Tokenize: lowercase `\w+`, drop English stopwords.
- Lazily rebuild from all `Chunk` rows when `_dirty` after ingest/delete (`invalidate()`).
- Scores with `BM25Okapi`; zeros out disallowed ids when filtering.

---

## 5.5 Retrieval (top-k, filters, hybrid, rerank)

**Orchestrator:** ⭐ `backend/app/retrieval/hybrid.py` → `retrieve(...)`  
**Also exposed by:** `POST /search` (`api/search.py`) with `mode`.

| Mode | Behavior |
|---|---|
| `vector` | Embed query → FAISS only |
| `keyword` | BM25 only |
| `hybrid` | Both → RRF merge |
| `hybrid_rerank` | hybrid then cross-encoder (default for `/query`) |

**Knobs (`config.py`):**

- `top_k_candidates = 20` — pool size before / for rerank  
- `top_k_final = 5` — chunks sent to the answer prompt  

**Document filter:** `document_ids` on request → `_allowed_chunk_ids` → passed into FAISS selector and BM25 score mask.

**RRF (`fusion.py`):** for each list, `score[id] += 1/(60 + rank)`.

**Reranker (`reranker.py`):**

- Lazy-loads `CrossEncoder(settings.reranker_model)`.
- `warm_up()` started in a daemon thread at app lifespan (`main.py`) so first query is less cold.
- `/query` path: if `RerankerUnavailable`, falls back to `mode="hybrid"` and sets `retrieval_degraded=True` (`nodes.retrieve_chunks`).
- `/search` path: same exception becomes **HTTP 503** (no silent fallback) — useful when you are measuring rerank.

**Lookup:** `load_chunks` (`lookup.py`) joins `Chunk` + `Document`, preserves ranking order, skips orphan vector ids.

---

## 5.6 Prompt building and context assembly

**File:** ⭐ `backend/app/graph/nodes.py` → `generate_answer`

If no chunks:

> “I couldn't find anything relevant… Try rephrasing…”

Else builds:

```text
[Source 1 - filename.pdf]
{chunk text}

[Source 2 - ...]
...
```

Then instructs the model to:

- answer using **ONLY** the CONTEXT  
- say it doesn’t know if missing  
- cite like `[Source 2]` or `[Source 1][Source 3]`  

Temperature `0.2`, `max_output_tokens=1024` via `generate_with_retry`.

**Rewrite prompt** (`rewrite_query`): short standalone search query; keep names/codes; do not answer; temperature `0`, max 64 tokens. On failure, uses the original question.

---

## 5.7 LLM call and response generation

**Client helper:** `backend/app/gemini_client.py` → `generate_with_retry`

- Model: `settings.gemini_generation_model`  
- Retries: up to 3 for 429/5xx with backoff  
- Returns stripped text or `""`

**Groundedness audit** (`check_groundedness`):

- Skips / returns `False` if no chunks or the canned “couldn’t find anything” answer.  
- Otherwise second prompt: “Reply with exactly one word: YES or NO.”  
- Parses `verdict.strip().upper().startswith("Y")`.  
- On failure: `is_grounded = None` (unknown), not a hard error.

**Pipeline wiring:** `backend/app/graph/pipeline.py`

```
rewrite_query → retrieve_chunks → generate_answer → check_groundedness → END
```

State type: `PipelineState` in `graph/state.py`.

**Tracing:** `Tracer` in `tracing/tracer.py` records ms per stage; returned as `trace.stages_ms` + `total_ms`.

---

## 5.8 API / backend layer

**App factory:** `backend/app/main.py`

| Route | Module | Role |
|---|---|---|
| `POST /ingest` | `api/ingest.py` | Upload → 202 job |
| `GET /jobs/{job_id}` | `api/ingest.py` | Poll progress |
| `GET /documents` | `api/documents.py` | List |
| `DELETE /documents/{id}` | `api/documents.py` | Delete DB rows, FAISS ids, files; invalidate BM25 + cache |
| `POST /search` | `api/search.py` | Retrieval microscope |
| `POST /query` | ⭐ `api/query.py` | Full RAG pipeline |
| `GET /health` | `main.py` | `{"status":"ok"}` for Compose healthcheck |

**Request/response models:** `backend/app/schemas/models.py` (`QueryRequest`, `QueryResponse`, `Citation`, `SearchRequest`, …).

**Auth:** **None in this codebase.** Any client that can reach the port can ingest/query/delete. Say this honestly in interviews.

**Error handling patterns that exist:**

| Situation | Behavior |
|---|---|
| Bad file type / empty | 400 |
| Too large | 413 |
| Duplicate hash | 409 |
| Missing job/doc | 404 |
| Gemini API error on query | 502 |
| Reranker down on `/search` | 503 |
| Reranker down on `/query` | degrade to hybrid |
| Embed/generate retries | backoff in embeddings + gemini_client |

**Cache on `/query`:** `ResponseCache` (`cache/response_cache.py`) — TTL default 600s; version baked into key; `bump_version()` on ingest complete and document delete. Cached responses set `cached=True`.

> Note: `settings.cache_ttl_seconds` exists in `config.py`, but `query_cache = ResponseCache()` is constructed **without** passing that setting. Effective TTL is the class default `600`, which happens to match the config default. Worth knowing if you change only the env/config field.

---

## 5.9 Frontend (Streamlit)

**File:** `frontend/app.py`  
**Config:** `BACKEND_URL` from `st.secrets` → else env → else `http://localhost:8000`

Features that exist:

- File uploader (pdf/txt/md), ingest button, progress fragment  
- Document list + delete  
- Search scope selectbox (all docs or one file) → `document_ids`  
- Chat input → `POST /query`  
- Shows answer, groundedness / degraded / cached badges  
- Citations expander (score shown as a logistic “% match”)  
- Pipeline trace expander  
- Local `st.session_state.history` (UI only — **not** sent back to the model as multi-turn memory)

**CLI:** no separate CLI beyond `eval/run_eval.py` and `uvicorn` / `streamlit` commands.

---

## 5.10 Evaluation harness

**Files:** `eval/run_eval.py`, `eval/eval_dataset.json`

1. **Retrieval:** for modes `vector|keyword|hybrid|hybrid_rerank`, measure whether top-5 hits include `expected_source_filename` (document-level Recall@5 proxy).  
2. **Pipeline:** call `/query`; score if `expected_answer_contains` appears in the answer (case-insensitive); also grounded rate + latency.  
3. Writes `eval/results/latest_run.json`.

Dataset in repo is filled with OOP questions targeting `oops_demo.pdf` (you must have that file ingested for scores to mean anything).

**Gap:** README says `pip install -r requirements.txt` under `eval/`, but **there is no `eval/requirements.txt`** — the script needs `requests` (present in `frontend/requirements.txt`).
