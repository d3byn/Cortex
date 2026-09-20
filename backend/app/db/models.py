import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field

def new_job_id() -> str:
    return uuid.uuid4().hex

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_type: str
    content_hash: str = Field(index=True)             
    num_chunks: int = 0
    created_at: datetime = Field(default_factory=utcnow)

class Chunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True) #FAISS ID
    document_id: int = Field(foreign_key="document.id", index=True)
    chunk_index: int                                  
    text: str

class Job(SQLModel, table=True):
    id: str = Field(default_factory=new_job_id, primary_key=True)
    filename: str
    status: str = "queued"                            
    progress: int = 0                                 
    stage: Optional[str] = None                       
    error: Optional[str] = None
    document_id: Optional[int] = Field(default=None, foreign_key="document.id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)