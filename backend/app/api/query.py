import logging
from fastapi import APIRouter, HTTPException
from google.genai import errors
from app.cache.response_cache import query_cache
from app.graph.pipeline import compiled_pipeline
from app.schemas.models import Citation, QueryRequest, QueryResponse
from app.tracing.tracer import Tracer

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["query"])

@router.post("/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    cache_key = query_cache.make_key(question=req.question, document_ids=req.document_ids)
    cached = query_cache.get(cache_key)
    if cached is not None:
        return QueryResponse(**{**cached.model_dump(), "cached": True})

    tracer = Tracer()
    initial_state = {"question": req.question, "document_ids": req.document_ids, "tracer": tracer}

    try:
        final_state = compiled_pipeline.invoke(initial_state)
    except errors.APIError as exc:
        logger.error("Query pipeline failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"The language model service failed: {exc.code}")

    response = QueryResponse(
        answer=final_state["answer"],
        citations=[
            Citation(chunk_id=c.chunk_id, document_id=c.document_id, filename=c.filename,
                     chunk_index=c.chunk_index, score=round(c.score, 4), text=c.text)
            for c in final_state["chunks"]
        ],
        search_query=final_state["search_query"],
        is_grounded=final_state["is_grounded"],
        retrieval_degraded=final_state["retrieval_degraded"],
        trace=tracer.as_dict(),
    )
    query_cache.set(cache_key, response)
    return response