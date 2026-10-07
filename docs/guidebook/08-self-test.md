# 15. Self-test — 15 questions about *your* project

← [Cheat sheet](07-cheat-sheet-glossary-revision.md) · [Index](../CORTEX_GUIDEBOOK.md)

Try to answer from memory. Then expand the answer. Re-test until you can do all fifteen cold.

---

### 1. Name the four LangGraph nodes in order.

<details>
<summary>Show answer</summary>

`rewrite_query` → `retrieve_chunks` → `generate_answer` → `check_groundedness`  
(Wired in `backend/app/graph/pipeline.py`, implemented in `backend/app/graph/nodes.py`.)

</details>

---

### 2. What are the default `chunk_size` and `chunk_overlap`?

<details>
<summary>Show answer</summary>

900 and 150 characters (`backend/app/config.py`), applied in `chunk_text` (`ingestion/chunker.py`).

</details>

---

### 3. Why does Cortex L2-normalize vectors before FAISS search?

<details>
<summary>Show answer</summary>

With unit-length vectors, inner product equals cosine similarity. The index is `IndexFlatIP` (`retrieval/vector_store.py`).

</details>

---

### 4. What HTTP status does a successful upload return, and why not 200?

<details>
<summary>Show answer</summary>

**202 Accepted** — processing continues in a background task; the client should poll `/jobs/{job_id}` (`api/ingest.py`).

</details>

---

### 5. How are duplicate uploads detected?

<details>
<summary>Show answer</summary>

SHA-256 of file bytes stored as `Document.content_hash`. Matching hash → **409** (`api/ingest.py`), with a second check inside `process_document` before insert.

</details>

---

### 6. List the four `/search` modes.

<details>
<summary>Show answer</summary>

`vector`, `keyword`, `hybrid`, `hybrid_rerank` (`schemas/models.py`, `retrieval/hybrid.py`).

</details>

---

### 7. What happens on `/query` if the reranker model fails to load?

<details>
<summary>Show answer</summary>

`retrieve_chunks` catches `RerankerUnavailable`, retries with `mode="hybrid"`, sets `retrieval_degraded=True` (`graph/nodes.py`). The request still returns an answer.

</details>

---

### 8. Where is the FAISS index file on disk?

<details>
<summary>Show answer</summary>

`backend/storage/index/faiss.index` (via `settings.index_dir` in `config.py` / `vector_store.py`).

</details>

---

### 9. How does the response cache know documents changed?

<details>
<summary>Show answer</summary>

`query_cache.bump_version()` on successful ingest and on document delete. The version is part of `make_key`, so old entries never match (`cache/response_cache.py`).

</details>

---

### 10. What prompt instruction forces citation format in answers?

<details>
<summary>Show answer</summary>

In `generate_answer`, the model must cite facts like `[Source 2]` or `[Source 1][Source 3]`, using only the CONTEXT built as `[Source i - filename]` blocks (`graph/nodes.py`).

</details>

---

### 11. Name one PDF cleanup heuristic in the parser.

<details>
<summary>Show answer</summary>

Either: rejoin character-spaced glyphs (`_rejoin_spaced_glyphs`), or rejoin word-per-line pages (`_rejoin_word_per_line`), plus `\xa0` → space (`ingestion/parsers.py`).

</details>

---

### 12. What does `eval/run_eval.py` use as its “accuracy” proxy?

<details>
<summary>Show answer</summary>

Whether `expected_answer_contains` appears (case-insensitive) inside the `/query` answer text — a phrase-containment proxy, not a semantic judge.

</details>

---

### 13. Which id links a SQLite chunk to its FAISS vector?

<details>
<summary>Show answer</summary>

The chunk’s integer primary key (`Chunk.id`) is passed to `add_with_ids` — there is no separate mapping table (`db/models.py`, `vector_store.py`, `background.py`).

</details>

---

### 14. Give two production gaps you would admit unprompted.

<details>
<summary>Show answer</summary>

Any two from the real list: no auth; FastAPI BackgroundTasks aren’t durable; SQLite/FAISS single-node; no unit test suite; no multi-turn memory; groundedness is another LLM; missing `eval/requirements.txt`; etc. (See chapter 9.)

</details>

---

### 15. Recite your 30-second pitch without looking.

<details>
<summary>Show answer</summary>

Sample: “Cortex is a hybrid-retrieval RAG system over my own PDF, TXT, and Markdown files. It embeds chunks into FAISS, also searches with BM25, fuses ranks with RRF, reranks with a cross-encoder, answers with Gemini using only retrieved context and citations, and runs a second LLM check for groundedness. I built it to be measurable and honest about failures, not just a demo chatbot.”  
(Full versions in `01-pitch-and-overview.md`.)

</details>

---

## After the self-test

- Re-open any ⭐ file you hesitated on.  
- Skim [last-minute revision](07-cheat-sheet-glossary-revision.md#14-last-minute-revision-page).  
- Optional live drill: start the stack, upload a short TXT, hit `/search` in all four modes, then `/query`, and explain the JSON out loud.
