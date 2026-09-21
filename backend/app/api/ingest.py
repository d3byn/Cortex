import hashlib
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select
from app.config import settings
from app.db.models import Document, Job
from app.db.session import get_session
from app.ingestion.background import process_document
from app.ingestion.parsers import detect_file_type
from app.schemas.models import IngestResponse, JobStatus

router = APIRouter(tags=["ingestion"])

@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    # Detect file type
    filename = Path(file.filename or "").name
    try:
        file_type = detect_file_type(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Check file size
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB.")

    # Detect duplicate uploads by hashing the file content and checking the database for existing documents with the same hash.
    content_hash = hashlib.sha256(data).hexdigest() #hashing 
    existing = session.exec(select(Document).where(Document.content_hash == content_hash)).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This file was already uploaded as '{existing.filename}' (document id {existing.id}).",
        )

    # Create a new job in the database to track the ingestion process.
    job = Job(filename=filename)
    session.add(job)
    session.commit()
    job_id = job.id

    saved_path = settings.uploads_dir / f"{job_id}.{file_type}"
    saved_path.write_bytes(data) #write the uploaded file to disk

    # Hand the slow work to the background and answer immediately.
    background_tasks.add_task(process_document, job_id, saved_path, filename, file_type, content_hash)
    return IngestResponse(job_id=job_id, 
                          filename=filename, 
                          status="queued")


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatus(
        job_id=job.id,
        filename=job.filename,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
        error=job.error,
        document_id=job.document_id,
    )