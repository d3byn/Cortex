from pathlib import Path
from sqlmodel import Session, select
from app.config import settings
from app.db.models import Chunk, Document, Job, utcnow
from app.db.session import engine
from app.ingestion.chunker import chunk_text
from app.ingestion.parsers import parse_file
from app.retrieval.embeddings import embed_texts
from app.retrieval.vector_store import vector_store
from app.retrieval.keyword_store import keyword_store

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

def process_document(
    job_id: str, saved_path: Path, filename: str, file_type: str, content_hash: str
) -> None:
    try:
        _update_job(job_id, status="processing", progress=5, stage="Reading file")
        text = parse_file(saved_path, file_type)

        _update_job(job_id, progress=15, stage="Splitting into chunks")
        pieces = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        if not pieces:
            raise ValueError("The file produced no text chunks.")

        # SLOW, can-fail step FIRST, while NO database transaction is open.
        def on_progress(done: int, total: int) -> None:
            _update_job(job_id, progress=15 + int(75 * done / total),
                        stage=f"Embedding chunks ({done}/{total})")

        vectors = embed_texts(pieces, progress_cb=on_progress)

        #one short transaction that saves everything together.
        _update_job(job_id, progress=92, stage="Saving")
        with Session(engine) as session:
            if session.exec(select(Document).where(Document.content_hash == content_hash)).first():
                raise ValueError("This file has already been uploaded.")

            doc = Document(filename=filename, file_type=file_type,
                           content_hash=content_hash, num_chunks=len(pieces))
            session.add(doc)
            session.flush()

            rows = [Chunk(document_id=doc.id, chunk_index=i, text=p) for i, p in enumerate(pieces)]
            session.add_all(rows)
            session.flush() # chunk ids now exist
            chunk_ids = [row.id for row in rows]
            document_id = doc.id

            vector_store.add(vectors, chunk_ids) # vectors filed under the chunk ids
            try:
                session.commit()
            except Exception:
                vector_store.remove(chunk_ids) # undo so FAISS never keeps orphans
                raise
            keyword_store.invalidate() 

        _update_job(job_id, status="complete", progress=100, stage="Done", document_id=document_id)

    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        _update_job(job_id, status="failed", stage="Failed", error=str(exc))