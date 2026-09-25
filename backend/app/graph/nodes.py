import logging
from sqlmodel import Session
from app.config import settings
from app.db.session import engine
from app.gemini_client import generate_with_retry
from app.graph.state import PipelineState
from app.retrieval.hybrid import retrieve
from app.retrieval.reranker import RerankerUnavailable

logger = logging.getLogger("uvicorn.error")

def rewrite_query(state: PipelineState) -> dict:
    tracer = state["tracer"]
    with tracer.stage("rewrite_query"):
        question = state["question"]
        prompt = (
            "Rewrite the user's question as a short, standalone search query for a document search engine. Keep any specific names, codes or numbers exactly as written. Do not answer the question. Return ONLY the rewritten query.\n\n"
            f"Question: {question}"
        )
        try:
            rewritten = generate_with_retry(prompt, temperature=0, max_output_tokens=64)
        except Exception as exc:
            logger.warning("rewrite_query failed, using the original question: %s", exc)
            rewritten = ""
    return {"search_query": rewritten or question}

def retrieve_chunks(state: PipelineState) -> dict:
    """Hybrid search (vector + keyword + fusion), with reranking as a best-effort extra."""
    tracer = state["tracer"]
    with tracer.stage("retrieve"):
        with Session(engine) as session:
            try:
                chunks = retrieve(
                    session, state["search_query"], mode="hybrid_rerank",
                    top_k=settings.top_k_final, candidates=settings.top_k_candidates,
                    document_ids=state.get("document_ids"),
                )
                degraded = False
            except RerankerUnavailable as exc:
                logger.warning("Reranker unavailable, falling back to hybrid search: %s", exc)
                chunks = retrieve(
                    session, state["search_query"], mode="hybrid",
                    top_k=settings.top_k_final, candidates=settings.top_k_candidates,
                    document_ids=state.get("document_ids"),
                )
                degraded = True
    return {"chunks": chunks, "retrieval_degraded": degraded}

_NO_CONTEXT_ANSWER = (
    "I couldn't find anything relevant to that question in the ingested documents. Try rephrasing, or check that the right document has been uploaded."
)

def generate_answer(state: PipelineState) -> dict:
    tracer = state["tracer"]
    with tracer.stage("generate_answer"):
        chunks = state["chunks"]
        if not chunks:
            return {"answer": _NO_CONTEXT_ANSWER}

        context = "\n\n".join(f"[Source {i+1} - {c.filename}]\n{c.text}" for i, c in enumerate(chunks))
        prompt = (
            "Answer the question using ONLY the CONTEXT below. If the context does not contain the answer, say you don't know - do not use outside knowledge. Cite the source of every fact you use, like [Source 2]. Multiple sources may support one fact: [Source 1][Source 3].\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION: {state['question']}\n\n"
            "ANSWER:"
        )
        try:
            answer = generate_with_retry(prompt, temperature=0.2, max_output_tokens=1024)
        except Exception as exc:
            logger.error("generate_answer failed: %s", exc)
            raise
    return {"answer": answer or "The model returned an empty answer. Please try again."}

def check_groundedness(state: PipelineState) -> dict:
    tracer = state["tracer"]
    with tracer.stage("check_groundedness"):
        chunks = state["chunks"]
        if not chunks or state["answer"] == _NO_CONTEXT_ANSWER:
            return {"is_grounded": False}

        context = "\n\n".join(c.text for c in chunks)
        prompt = (
            "Does the ANSWER rely only on facts present in the CONTEXT, with no outside knowledge added? Reply with exactly one word: YES or NO.\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"ANSWER:\n{state['answer']}\n\n"
            "YES or NO:"
        )
        try:
            verdict = generate_with_retry(prompt, temperature=0, max_output_tokens=5)
            is_grounded = verdict.strip().upper().startswith("Y")
        except Exception as exc:
            logger.warning("check_groundedness failed, marking result as unknown: %s", exc)
            is_grounded = None
    return {"is_grounded": is_grounded}