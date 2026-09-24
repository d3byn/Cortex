from dataclasses import dataclass
from typing import List, Tuple, Optional
from sqlmodel import Session, col, select
from app.db.models import Chunk, Document

@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    filename: str
    chunk_index: int
    text: str
    score: float
    vector_rank: Optional[int] = None # position in the FAISS list (None = not found there)
    keyword_rank: Optional[int] = None # position in the BM25 list

def load_chunks(session: Session, scored_ids: List[Tuple[int, float]]) -> List[RetrievedChunk]:
    """Turn [(chunk_id, score), ...] from FAISS into full chunks with text + filename."""
    if not scored_ids:
        return []
    ids = [chunk_id for chunk_id, _ in scored_ids]
    rows = session.exec(
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(col(Chunk.id).in_(ids))
    ).all()
    by_id = {chunk.id: (chunk, doc) for chunk, doc in rows}

    results = []
    for chunk_id, score in scored_ids: # keep FAISS's best-first order
        if chunk_id not in by_id: # vector without a chunk: skip, never crash
            continue
        chunk, doc = by_id[chunk_id]
        results.append(RetrievedChunk(chunk_id, doc.id, doc.filename, chunk.chunk_index, chunk.text, score))
    return results