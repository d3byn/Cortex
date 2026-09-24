from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class IngestResponse(BaseModel):
    job_id: str
    filename: str
    status: str

class JobStatus(BaseModel):
    job_id: str
    filename: str
    status: str
    progress: int
    stage: Optional[str] = None
    error: Optional[str] = None
    document_id: Optional[int] = None

class DocumentInfo(BaseModel):
    id: int
    filename: str
    file_type: str
    num_chunks: int
    created_at: datetime

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)

class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    filename: str
    chunk_index: int
    score: float
    text: str