from typing import List
from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors
from sqlmodel import Session
from app.config import settings
from app.db.session import get_session
from app.retrieval.hybrid import retrieve
from app.retrieval.reranker import RerankerUnavailable
from app.schemas.models import SearchHit, SearchRequest

router = APIRouter(tags=["search"])

@router.post("/search", response_model=List[SearchHit])
def search(req: SearchRequest, session: Session = Depends(get_session)):
    """Retrieval only (no answer generation): a microscope on the search pipeline."""
    try:
        chunks = retrieve(
            session,
            req.query,
            mode=req.mode,
            top_k=req.top_k,
            candidates=max(settings.top_k_candidates, req.top_k),
            document_ids=req.document_ids,
        )
    except errors.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding service error: {exc.code}")
    except RerankerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return [
        SearchHit(
            chunk_id=c.chunk_id, document_id=c.document_id, filename=c.filename,
            chunk_index=c.chunk_index, score=round(c.score, 4),
            vector_rank=c.vector_rank, keyword_rank=c.keyword_rank, text=c.text,
        )
        for c in chunks
    ]