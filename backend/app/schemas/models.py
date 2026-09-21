from datetime import datetime
from typing import Optional
from pydantic import BaseModel

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