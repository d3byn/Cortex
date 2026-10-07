# 1–2. Pitch and spoken explanation

← [Index](../CORTEX_GUIDEBOOK.md) · Next: [Architecture & RAG →](02-architecture-and-rag.md)

---

## 1. 30-second pitch

**What Cortex is:**  
Cortex is a **document Q&A system**. You upload PDF, TXT, or Markdown files. You ask questions in plain English. It finds the relevant passages in *your* files, answers from those passages only, and shows citations (which file / which chunk). If the docs do not contain the answer, it is designed to say it does not know — not invent facts.

**Problem it solves:**  
Large language models alone can sound confident while being wrong (**hallucination**). Companies and students need answers grounded in *their* notes, manuals, or policies — with proof of where the answer came from.

**Who uses it:**  
Anyone with private documents who wants searchable, citation-backed answers — e.g. a student studying notes, an engineer querying runbooks, or a team querying internal PDFs. In this repo it is a personal / demo platform (Streamlit UI + FastAPI), not a multi-tenant SaaS product.

**One line for an interviewer:**  
> “Cortex is a hybrid-retrieval RAG API over my own documents: FAISS + BM25 fused with RRF, cross-encoder reranking, Gemini for embeddings and answers, plus a second LLM call that checks whether the answer stayed grounded.”

---

## 2. 2-minute explanation (speak this aloud)

Practice until you can say something like this without reading:

> Cortex is a grounded RAG system I built to answer questions over my own PDF, TXT, and Markdown files.
>
> **Ingestion:** When I upload a file, the API accepts it asynchronously. A background job parses the file, cleans messy PDF text, splits it into overlapping chunks of about 900 characters, embeds those chunks with Gemini, and stores the text in SQLite and the vectors in FAISS. The chunk’s database primary key is also its FAISS ID, so text and vectors cannot drift apart. Embedding happens *before* the DB transaction, so a failure leaves either everything saved or nothing.
>
> **Query:** When I ask a question, a LangGraph pipeline runs four steps: (1) rewrite the question into a short search query, (2) hybrid retrieve — semantic search with FAISS and keyword search with BM25, merge ranks with Reciprocal Rank Fusion, then optionally rerank with a cross-encoder, (3) generate an answer with Gemini using only the retrieved context and inline citations, (4) a second, independent Gemini call that answers YES or NO to whether the answer is grounded in that context.
>
> **Why it’s more than a toy RAG demo:** I can compare retrieval modes through a `/search` API and an eval script that measures Recall@5. Failures degrade gracefully — if the reranker cannot load, the pipeline falls back to hybrid search. A response cache invalidates when documents change. The frontend is Streamlit; the backend is FastAPI, all runnable with Docker Compose.

**If they interrupt after 30 seconds**, stop at the hybrid retrieval + groundedness sentence. That is the “wow” of the project.

**If they ask “what’s unique?”**, say:

1. Hybrid retrieval with measurable lift (`eval/run_eval.py`)  
2. Groundedness audit as a separate LLM call (`check_groundedness` in `backend/app/graph/nodes.py`)  
3. Chunk ID = FAISS ID + embed-before-commit (`backend/app/ingestion/background.py`, `backend/app/retrieval/vector_store.py`)
