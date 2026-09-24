from typing import List

from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors
from sqlmodel import Session

from app.db.session import get_session
from app.retrieval.embeddings import embed_query
from app.retrieval.lookup import load_chunks
from app.retrieval.vector_store import vector_store
from app.schemas.models import SearchHit, SearchRequest

router = APIRouter(tags=["search"])


@router.post("/search", response_model=List[SearchHit])
def search(req: SearchRequest, session: Session = Depends(get_session)):
    """Retrieval only (no answer generation): handy for seeing what the index finds."""
    try:
        query_vector = embed_query(req.query)
    except errors.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding service error: {exc.code}")

    scored = vector_store.search(query_vector, req.top_k)
    return [
        SearchHit(chunk_id=c.chunk_id, document_id=c.document_id, filename=c.filename,
                  chunk_index=c.chunk_index, score=round(c.score, 4), text=c.text)
        for c in load_chunks(session, scored)
    ]