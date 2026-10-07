# 11. Interview Q&A bank

← [Design & setup](05-design-challenges-setup.md) · [Index](../CORTEX_GUIDEBOOK.md) · Next: [Cheat sheet →](07-cheat-sheet-glossary-revision.md)

Speak these as short paragraphs. Prefer “I” statements. When you cite a file, you can open it live if they ask.

---

## A. Project overview and motivation

**Q1. What is Cortex?**  
Cortex is a document intelligence API I built. You upload PDF, TXT, or Markdown, ask questions, and get answers grounded in retrieved passages with citations. The UI is Streamlit; the backend is FastAPI with a LangGraph RAG pipeline.

**Q2. Why did you build it?**  
I wanted something stronger than a “embed into a vector DB and hope” demo. I cared about hybrid retrieval I can measure, consistent storage between text and vectors, and an explicit groundedness check so the system can admit when it’s unsure.

**Q3. Who is the user?**  
Anyone with private documents who needs Q&A with sources — students, engineers with runbooks, small teams. It’s a single-node demo platform, not a multi-tenant product yet.

**Q4. What’s the biggest technical idea you’re proud of?**  
Two things: (1) chunk primary key equals FAISS id, so mappings can’t drift; (2) embed before the DB transaction, then commit text and vectors together, rolling FAISS back if commit fails — see `ingestion/background.py` and `vector_store.py`.

**Q5. Walk me through a request end to end.**  
Upload hits `/ingest`, returns a job id, background parse/chunk/embed/save. Question hits `/query`: optional cache hit; else rewrite → hybrid retrieve → generate with citations → groundedness YES/NO → return answer, citations, and stage timings.

**Q6. What does “grounded” mean in your product?**  
A second Gemini call reads the same retrieved context and the answer and must reply YES or NO if the answer used only those facts. The UI shows a badge from `is_grounded`. It’s a soft check, not a formal proof.

---

## B. RAG and LLM concepts

**Q7. What is RAG in one sentence?**  
Retrieve relevant document pieces first, then generate the answer using those pieces as context so the model isn’t guessing from memory alone.

**Q8. Why not fine-tune instead of RAG?**  
Fine-tuning is heavy, slow to update when docs change, and still can hallucinate. RAG lets me add or delete a PDF and immediately change what the system can cite — which matches Cortex’s ingest/delete + cache invalidation design.

**Q9. What is an embedding?**  
A numeric vector that represents meaning. Similar texts land closer together. Cortex uses Gemini embeddings in `retrieval/embeddings.py` for chunks and for the search query.

**Q10. What’s the difference between bi-encoder and cross-encoder?**  
Bi-encoder embeds query and docs separately (fast retrieval — our FAISS path). Cross-encoder scores a query–passage pair together (slower, usually sharper — our `reranker.py`). I use bi-encoder to fetch candidates and cross-encoder to reorder them.

**Q11. What is chunking and why overlap?**  
Long docs don’t fit cleanly into one vector or one prompt, so I split them (~900 chars). Overlap (~150) means ideas on boundaries aren’t cut in half. Implemented in `chunker.py`.

**Q12. What is hallucination and how do you reduce it?**  
Confident false statements. I reduce it with retrieval, a strict “ONLY use CONTEXT” prompt, citations, an empty-retrieval refusal message, and the groundedness audit. I don’t claim I eliminated it.

**Q13. Temperature — what do you use and why?**  
Rewrite and groundedness use temperature 0 for determinism. Answer generation uses 0.2 for a little natural phrasing without wild creativity — see `nodes.py`.

**Q14. What is Reciprocal Rank Fusion?**  
A way to merge multiple ranked lists without comparing raw scores. Each appearance of an id adds `1/(k + rank)`. In Cortex, `k=60` in `fusion.py`, merging FAISS and BM25 lists.

**Q15. Why BM25 in addition to vectors?**  
Exact tokens — product codes, method names like `sound()`, acronyms — often match better with keywords. Hybrid covers both paraphrase and exact match.

---

## C. Backend and system design

**Q16. Why FastAPI?**  
Typed request models with Pydantic, automatic OpenAPI at `/docs`, dependency-injected DB sessions, and easy background tasks for ingest. Fits a Python ML/RAG stack.

**Q17. How does async ingest work?**  
`POST /ingest` validates and stores the file, creates a Job, schedules `process_document` with `BackgroundTasks`, returns 202 immediately. The UI polls `GET /jobs/{id}`.

**Q18. What happens if the server restarts mid-ingest?**  
On startup, `init_db` marks leftover `queued`/`processing` jobs failed and tells the user to re-upload. BackgroundTasks aren’t durable — I’d use a real queue in production.

**Q19. How do you avoid partial writes?**  
Embed first outside a transaction. Then one short transaction creates Document + Chunks, adds FAISS vectors keyed by those chunk ids, commits; if commit fails, remove those FAISS ids. Keyword index is invalidated after success.

**Q20. How does caching work?**  
In-memory `ResponseCache` with TTL. Cache keys include a version integer bumped on ingest/delete, so stale answers can’t be served after corpus changes (`cache/response_cache.py`, called from query/ingest/documents).

**Q21. Is there authentication?**  
Not in this repo. For production I’d put an API gateway or auth middleware and isolate documents per user. I’m explicit about that as a limitation.

**Q22. How do you handle Gemini rate limits?**  
`embeddings.py` and `gemini_client.py` retry on 429 and transient 5xx with exponential backoff and jitter.

**Q23. Why LangGraph if the graph is linear?**  
It makes stages explicit and the state typed. Today it’s a straight line; the structure is ready for conditional edges later, like retry retrieval if ungrounded — which I haven’t built yet.

**Q24. How do you observe latency?**  
A `Tracer` context manager around each stage records milliseconds; `/query` returns `trace.stages_ms` and `total_ms`. The Streamlit UI shows it in an expander.

---

## D. Database and vector search

**Q25. What’s stored where?**  
SQLite holds documents, chunk text, jobs. FAISS holds one vector per chunk id. Uploaded raw files live under `storage/uploads/`. BM25 is rebuilt in memory from SQLite.

**Q26. Why is the chunk id also the FAISS id?**  
A separate mapping table can desync. If the same integer means the same chunk everywhere, `load_chunks` is a simple join/lookup and reconcile can compare id sets.

**Q27. What similarity metric do you use?**  
Cosine similarity via L2-normalized vectors + inner product (`IndexFlatIP`) in `vector_store.py`.

**Q28. Why IndexFlatIP?**  
Exact search, simple, fine for small/medium personal corpora. At large n I’d move to approximate indexes (IVF/HNSW) or an external vector DB.

**Q29. How do document filters work?**  
`document_ids` → set of allowed chunk ids → FAISS `IDSelectorBatch` and BM25 score masking *before* ranking, so you don’t fetch global top-k and filter after (which can return too few).

**Q30. How do you keep FAISS and SQLite consistent on delete?**  
Delete chunks/jobs/document in SQL, invalidate BM25 and bump cache, then `vector_store.remove(chunk_ids)` and unlink upload files (`api/documents.py`).

**Q31. What does reconcile do at startup?**  
Compares FAISS ids to Chunk ids: removes stray vectors; logs how many chunks lack vectors (those need re-upload).

---

## E. Debugging, testing, and deployment

**Q32. How do you debug a bad answer?**  
Check `/search` with different modes for the same question; inspect vector_rank vs keyword_rank on hits; read the rewritten `search_query` and stage timings from `/query`; verify the citation texts actually contain the fact.

**Q33. How do you evaluate quality?**  
`eval/run_eval.py` measures Recall@5 per retrieval mode against expected source filenames, plus end-to-end phrase containment, grounded rate, and latency. It’s a harness, not a perfect metric — I also read answers manually.

**Q34. How do you deploy locally?**  
Docker Compose builds backend and frontend, mounts storage, healthchecks `/health`, frontend waits until backend is healthy.

**Q35. What’s in the backend Docker image that’s special?**  
It installs CPU PyTorch before requirements so the cross-encoder can run, plus `libgomp1`.

**Q36. Do you have unit tests?**  
Not in this repository. If asked what I’d add first: chunker boundary tests, RRF ordering tests, vector_store add/remove/reconcile tests, and an API test with a fake Gemini client.

**Q37. What breaks if you change the embedding model?**  
Vector dimension may change; `vector_store.add` refuses mismatched dims and tells you to clear `backend/storage/` and re-ingest.

---

## F. “Why did you choose X over Y?”

**Q38. Why FAISS over Pinecone/Chroma?**  
For a portfolio/single-node project I wanted zero external service and full control. FAISS in-process is enough; I’d revisit for multi-tenant cloud scale.

**Q39. Why SQLite over Postgres?**  
Operational simplicity for a demo. Postgres when I need concurrent writers, managed backups, and multiple API replicas.

**Q40. Why Gemini over OpenAI?**  
Pragmatic: one key for embeddings and chat, models configured in `.env`, SDK already wired. The architecture doesn’t depend on Gemini-specific retrieval — only the client layer does.

**Q41. Why Streamlit over a React app?**  
Fastest path to a usable chat + upload UX for a backend-heavy project. The API is the real product surface (`/docs`).

**Q42. Why character-based chunking vs token-based?**  
The code uses character windows with punctuation-aware cuts — simple and dependency-light. Token-aware chunking would align better with model context limits; I could switch later with a tokenizer.

**Q43. Why not agentic multi-step tool calling?**  
I scoped to a reliable retrieve-then-generate loop with measurement. Agents add power and failure modes; I’d add tools after the base RAG metrics are solid.

---

## G. Tough / tricky follow-ups

**Q44. Can’t the groundedness model just rubber-stamp YES?**  
Yes — it’s another LLM. That’s why I also show citations for humans and keep temperature 0 on the judge. Stronger approaches: entailment models, quote checking, or requiring extractive spans. I haven’t implemented those.

**Q45. What if retrieval returns irrelevant chunks but the model still answers from world knowledge?**  
The prompt forbids outside knowledge, and the judge should flag NO. If both fail, the UI can still mislead — so citations and `is_grounded=false` are signals for the user, not guarantees.

**Q46. Race: two identical uploads at once?**  
Hash check happens at request time and again inside the save transaction. There’s still no distributed lock; under concurrent workers you’d want a unique DB constraint on `content_hash` (indexed today, uniqueness not enforced as a constraint in the model) and transactional guarantees.

**Q47. Is BM25 rebuilt on every search?**  
Only when dirty after ingest/delete. Rebuild scans all chunks — fine for small corpora; for large ones I’d persist an inverted index.

**Q48. Does chat history affect answers?**  
No. Streamlit keeps display history only. Each `/query` is standalone. Multi-turn would need to send prior turns or a summary into rewrite/retrieve.

**Q49. How do you prevent prompt injection from documents?**  
I don’t have a dedicated sanitizer. Retrieved text is placed in CONTEXT; a malicious PDF could try to override instructions. Mitigations I’d discuss: clear delimiters, instruction prioritying, output filters, and not executing tool calls from docs. Not implemented here.

**Q50. What’s your biggest production gap?**  
Auth and durable background jobs first, then shared storage for multi-instance, then stronger evaluation and streaming UX.

**Q51. Show me where hybrid search could still fail.**  
If neither semantic neighbors nor shared keywords hit the right chunk — e.g. the user asks with synonyms BM25 doesn’t know and embeddings miss — top-k is wrong and generation can’t recover. That’s the classic “garbage in, garbage out” of RAG.

**Q52. Why return vector_rank and keyword_rank?**  
Debuggability. On `/search` hits I can see whether fusion preferred a vector-only or keyword-only document — essential when explaining eval lifts.
