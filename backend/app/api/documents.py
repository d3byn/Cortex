from typing import List
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.db.models import Document
from app.db.session import get_session
from app.schemas.models import DocumentInfo

router = APIRouter(tags=["documents"])

#Fetch all successfully stored documents from the database and return them to the client in a clean API format.
@router.get("/documents", response_model=List[DocumentInfo])
def list_documents(session: Session = Depends(get_session)):
    docs = session.exec(select(Document).order_by(Document.created_at.desc())).all()
    return [
        DocumentInfo(id=d.id, 
                     filename=d.filename, 
                     file_type=d.file_type,
                     num_chunks=d.num_chunks, 
                     created_at=d.created_at)
        for d in docs
    ]