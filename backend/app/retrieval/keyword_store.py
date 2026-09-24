import re
import threading
from typing import Collection, List, Optional, Tuple
import numpy as np
from rank_bm25 import BM25Okapi
from sqlmodel import Session, select
from app.db.models import Chunk
from app.db.session import engine

_TOKEN_RE = re.compile(r"\w+")
_STOPWORDS = frozenset(
    "a an and are as at be but by for from has have he her his i in is it its "
    "of on or she that the their them they this to was we were what when where "
    "which who will with you your".split()
)

def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]

class KeywordStore:
    """BM25 keyword search over every chunk. Rebuilt lazily whenever the data changes."""

    def __init__(self):
        self._lock = threading.RLock()
        self._dirty = True
        self._bm25: Optional[BM25Okapi] = None
        self._ids: List[int] = []

    def invalidate(self) -> None:
        """Call after chunks are added or deleted. Cheap: the rebuild happens on the next search."""
        self._dirty = True

    def _rebuild(self) -> None:
        self._dirty = False
        with Session(engine) as session:
            rows = session.exec(select(Chunk.id, Chunk.text)).all()
        self._ids = [chunk_id for chunk_id, _ in rows]
        corpus = [tokenize(text) for _, text in rows]
        self._bm25 = BM25Okapi(corpus) if any(corpus) else None

    def search(
        self, query: str, k: int, allowed_ids: Optional[Collection[int]] = None
    ) -> List[Tuple[int, float]]:
        """Return up to k (chunk_id, bm25_score) pairs, best first. Only chunks that share a word with the query."""
        with self._lock:
            if self._dirty:
                self._rebuild()
            if self._bm25 is None:
                return []
            query_tokens = tokenize(query)
            if not query_tokens:
                return []
            scores = np.array(self._bm25.get_scores(query_tokens), dtype="float64")
            if allowed_ids is not None:
                allowed = set(allowed_ids)
                scores[[cid not in allowed for cid in self._ids]] = 0.0   # scope BEFORE ranking
            order = np.argsort(-scores)[:k]
            return [(self._ids[i], float(scores[i])) for i in order if scores[i] > 0]

keyword_store = KeywordStore()