from typing import List, Literal, Optional, Sequence, Set
from sqlmodel import Session, col, select
from app.db.models import Chunk
from app.retrieval.embeddings import embed_query
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword_store import keyword_store
from app.retrieval.lookup import RetrievedChunk, load_chunks
from app.retrieval.reranker import reranker
from app.retrieval.vector_store import vector_store

Mode = Literal["vector", "keyword", "hybrid", "hybrid_rerank"]

def _allowed_chunk_ids(session: Session, document_ids: Optional[Sequence[int]]) -> Optional[Set[int]]:
    """None means 'search everything'. Otherwise, the ids of chunks in the chosen documents."""
    if document_ids is None:
        return None
    rows = session.exec(select(Chunk.id).where(col(Chunk.document_id).in_(list(document_ids)))).all()
    return set(rows)

def retrieve(
    session: Session,
    query: str,
    *,
    mode: Mode = "hybrid_rerank",
    top_k: int = 5,
    candidates: int = 20,
    document_ids: Optional[Sequence[int]] = None,
) -> List[RetrievedChunk]:
    allowed = _allowed_chunk_ids(session, document_ids)
    if allowed is not None and not allowed:
        return []

    # Two independent searches (each one only runs if the mode needs it).
    vector_hits: list = []
    keyword_hits: list = []
    if mode != "keyword":
        vector_hits = vector_store.search(embed_query(query), candidates, allowed)
    if mode != "vector":
        keyword_hits = keyword_store.search(query, candidates, allowed)

    # Decide the order.
    if mode == "vector":
        ordered = vector_hits
    elif mode == "keyword":
        ordered = keyword_hits
    else:
        ordered = reciprocal_rank_fusion(
            [[cid for cid, _ in vector_hits], [cid for cid, _ in keyword_hits]]
        )

    # Fetch text, and remember where each chunk ranked in each list (great for debugging).
    chunks = load_chunks(session, ordered[:candidates])
    vector_rank = {cid: r for r, (cid, _) in enumerate(vector_hits, start=1)}
    keyword_rank = {cid: r for r, (cid, _) in enumerate(keyword_hits, start=1)}
    for chunk in chunks:
        chunk.vector_rank = vector_rank.get(chunk.chunk_id)
        chunk.keyword_rank = keyword_rank.get(chunk.chunk_id)

    # Optional final precision step.
    if mode == "hybrid_rerank":
        chunks = reranker.rerank(query, chunks)

    return chunks[:top_k]