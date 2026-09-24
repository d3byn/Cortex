import random
import time
from typing import Callable, List, Optional
import numpy as np
from google.genai import errors, types
from app.config import settings
from app.gemini_client import client

EMBED_BATCH_SIZE = 50
# 429 → rate limited
# 500 → server error
# 502 → bad gateway
# 503 → service unavailable
# 504 → gateway timeout
_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 5

def _uses_prompt_prefixes() -> bool:
    """gemini-embedding-2 takes its task hint as text; -001 takes a task_type parameter."""
    return "embedding-2" in settings.gemini_embedding_model

def _format_document(chunk: str) -> str:
    return f"title: none | text: {chunk}" if _uses_prompt_prefixes() else chunk

def _format_query(question: str) -> str:
    return f"task: question answering | query: {question}" if _uses_prompt_prefixes() else question

def _config(task_type: str) -> Optional[types.EmbedContentConfig]:
    return None if _uses_prompt_prefixes() else types.EmbedContentConfig(task_type=task_type)

def _as_contents(texts: List[str]) -> List[types.Content]:
    # ONE Content per text. A bare list of strings can be read as "several parts of ONE item" and come back as a single vector, so they are explicit
    return [types.Content(parts=[types.Part(text=t)]) for t in texts]

def _embed_with_retry(texts: List[str], task_type: str) -> List[List[float]]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            result = client.models.embed_content(
                model=settings.gemini_embedding_model,
                contents=_as_contents(texts),
                config=_config(task_type),
            )
            break
        except errors.APIError as exc:
            if exc.code not in _RETRYABLE_CODES or attempt == _MAX_ATTEMPTS:
                raise
            time.sleep(min(2 ** attempt, 30) + random.random())   

    vectors = [e.values for e in result.embeddings]
    if len(vectors) != len(texts):
        raise RuntimeError(f"Sent {len(texts)} texts but got {len(vectors)} embeddings back.")
    return vectors

def embed_texts(
    texts: List[str],
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> np.ndarray:
    """Embed document chunks. Returns an (N, dim) float32 array, same order as `texts`."""
    if not texts:
        return np.zeros((0, 0), dtype="float32")

    vectors: List[List[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = [_format_document(t) for t in texts[start : start + EMBED_BATCH_SIZE]]
        vectors.extend(_embed_with_retry(batch, "RETRIEVAL_DOCUMENT"))
        if progress_cb is not None:
            progress_cb(len(vectors), len(texts))
    return np.array(vectors, dtype="float32")

def embed_query(text: str) -> np.ndarray:
    """Embed one question. Returns a (dim,) float32 array."""
    return np.array(_embed_with_retry([_format_query(text)], "RETRIEVAL_QUERY")[0], dtype="float32")