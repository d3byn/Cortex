from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select
from app.config import settings
from app.db.models import Chunk, Document, Job
from app.db.session import get_session
from app.retrieval.vector_store import vector_store
from app.schemas.models import DocumentInfo
from app.retrieval.keyword_store import keyword_store

router = APIRouter(tags=["documents"])

@router.get("/documents", response_model=List[DocumentInfo])
def list_documents(session: Session = Depends(get_session)):
    docs = session.exec(select(Document).order_by(Document.created_at.desc())).all()
    return [
        DocumentInfo(id=d.id, filename=d.filename, file_type=d.file_type,
                     num_chunks=d.num_chunks, created_at=d.created_at)
        for d in docs
    ]

@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    chunks = session.exec(select(Chunk).where(Chunk.document_id == document_id)).all()
    jobs = session.exec(select(Job).where(Job.document_id == document_id)).all()
    chunk_ids = [c.id for c in chunks]
    saved_files = [settings.uploads_dir / f"{j.id}.{doc.file_type}" for j in jobs]

    for row in [*chunks, *jobs, doc]:
        session.delete(row)
    session.commit()
    keyword_store.invalidate()

    vector_store.remove(chunk_ids)
    for path in saved_files:
        path.unlink(missing_ok=True)
    return Response(status_code=204)