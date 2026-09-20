from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]   
PROJECT_DIR = BACKEND_DIR.parent                    

class Settings(BaseSettings):
    #gemini
    gemini_api_key: str                                   
    gemini_generation_model: str = "gemini-3.1-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-2"

    #storage
    data_dir: Path = BACKEND_DIR / "storage"

    #chunking and retrieval
    chunk_size: int = 900
    chunk_overlap: int = 150
    top_k_candidates: int = 20
    top_k_final: int = 5

    model_config = SettingsConfigDict(env_file=PROJECT_DIR / ".env", 
                                      extra="ignore")

    @property
    def uploads_dir(self) -> Path:
        path = self.data_dir / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def index_dir(self) -> Path:
        path = self.data_dir / "index"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "app.db"


settings = Settings()