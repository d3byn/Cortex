import logging
import threading
from typing import List
from app.config import settings
from app.retrieval.lookup import RetrievedChunk
logger = logging.getLogger("uvicorn.error")

class RerankerUnavailable(RuntimeError):
    """The cross-encoder model could not be loaded (not installed, or no internet on first run)."""

class Reranker:
    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import CrossEncoder
                    self._model = CrossEncoder(settings.reranker_model)
                except Exception as exc:
                    raise RerankerUnavailable(
                        f"Could not load reranker '{settings.reranker_model}': {exc}"
                    ) from exc
            return self._model

    def warm_up(self) -> None:
        """Load the model in the background at startup so the first query isn't slow."""
        try:
            self._get_model()
            logger.info("Reranker model ready: %s", settings.reranker_model)
        except RerankerUnavailable as exc:
            logger.warning("%s", exc)

    def rerank(self, query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Score every (query, chunk) pair together and return chunks best-first."""
        if not chunks:
            return []
        model = self._get_model()
        scores = model.predict([(query, chunk.text) for chunk in chunks])
        for chunk, score in zip(chunks, scores):
            chunk.score = float(score)
        return sorted(chunks, key=lambda c: c.score, reverse=True)

reranker = Reranker()