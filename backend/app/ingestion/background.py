from pathlib import Path
from sqlmodel import Session, select
from app.config import settings
from app.db.models import Chunk, Document, Job, utcnow
from app.db.session import engine
from app.ingestion.chunker import chunk_text
from app.ingestion.parsers import parse_file

#Find a particular job in the database and update its status/progress/stage/etc
def _update_job(job_id: str, **fields) -> None:
    """Save progress in its own short session, so pollers see it immediately."""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        job.updated_at = utcnow()
        session.add(job)
        session.commit()


#main ingestion pipeline 
def process_document(
    job_id: str, saved_path: Path, filename: str, file_type: str, content_hash: str
) -> None:
    try:
        _update_job(job_id, status="processing", progress=5, stage="Reading file")
        text = parse_file(saved_path, file_type)

        _update_job(job_id, progress=30, stage="Splitting into chunks")
        pieces = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        if not pieces:
            raise ValueError("The file produced no text chunks.")

        _update_job(job_id, progress=60, stage="Saving to database")
        with Session(engine) as session:
            # Guard against two identical uploads racing each other.
            if session.exec(select(Document).where(Document.content_hash == content_hash)).first():
                raise ValueError("This file has already been uploaded.")

            doc = Document(filename=filename, file_type=file_type, content_hash=content_hash, num_chunks=len(pieces))
            session.add(doc)
            session.flush() # sends the INSERT now so doc.id exists, but does NOT commit yet

            session.add_all(
                Chunk(document_id=doc.id, chunk_index=i, text=piece)
                for i, piece in enumerate(pieces)
            )
            session.flush() # chunk ids now exist too (Stage 4 will use them for FAISS)

            # Stage 4 will embed the chunks and add them to FAISS right here,
            # BEFORE the commit. If anything fails, nothing is saved.

            document_id = doc.id # read it now - after commit the object is "expired"
            session.commit()

        _update_job(job_id, status="complete", progress=100, stage="Done", document_id=document_id)

    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        _update_job(job_id, status="failed", stage="Failed", error=str(exc))