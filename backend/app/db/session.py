from sqlmodel import Session, SQLModel, col, create_engine, select
from app.config import settings
from app.db.models import Job

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
)

#Handling orphaned jobs that were in progress when the server was restarted.
def fail_orphaned_jobs() -> None:
    with Session(engine) as session:
        stale = session.exec(
            select(Job).where(col(Job.status).in_(["queued", "processing"]))
        ).all()
        for job in stale:
            job.status = "failed"
            job.error = "Server restarted while this file was processing. Please upload it again."
            session.add(job)
        session.commit()

def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    fail_orphaned_jobs()

#database dependency 
def get_session():
    with Session(engine) as session:
        yield session