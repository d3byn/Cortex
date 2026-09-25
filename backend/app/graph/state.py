from typing import List, Optional, Sequence, TypedDict
from app.retrieval.lookup import RetrievedChunk
from app.tracing.tracer import Tracer

class PipelineState(TypedDict, total=False):
    #input
    question: str
    document_ids: Optional[Sequence[int]]
    tracer: Tracer # internal; stripped before the response is built

    #filled in by rewrite_query
    search_query: str

    #filled in by retrieve
    chunks: List[RetrievedChunk]
    retrieval_degraded: bool # True if the reranker was skipped due to an error

    #filled in by generate_answer
    answer: str

    #filled in by check_groundedness
    is_grounded: Optional[bool] # None = the check itself could not run