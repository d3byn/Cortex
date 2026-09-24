import os
import threading
from typing import List, Optional, Sequence, Set, Tuple, Collection
import faiss
import numpy as np
from app.config import settings

INDEX_PATH = settings.index_dir / "faiss.index"

class VectorStore:
    """A FAISS index that maps chunk ids -> vectors, saved to disk after every change."""

    def __init__(self, path=INDEX_PATH):
        self.path = path
        self._lock = threading.RLock()          # background threads write, requests read
        self.index: Optional[faiss.IndexIDMap] = None
        if self.path.exists():
            self.index = faiss.read_index(str(self.path))

    # info
    @property
    def count(self) -> int:
        return 0 if self.index is None else self.index.ntotal

    @property
    def dim(self) -> Optional[int]:
        return None if self.index is None else self.index.d

    def all_ids(self) -> Set[int]:
        with self._lock:
            if self.index is None:
                return set()
            return set(faiss.vector_to_array(self.index.id_map).tolist())

    # persistence
    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        faiss.write_index(self.index, str(tmp))
        os.replace(tmp, self.path)              # atomic swap: a crash never leaves a half-written index

    # write
    def add(self, vectors: np.ndarray, ids: Sequence[int]) -> None:
        vectors = np.array(vectors, dtype="float32", copy=True)
        if vectors.ndim != 2 or len(vectors) != len(ids):
            raise ValueError("vectors must be 2-D with one row per id")
        id_array = np.asarray(ids, dtype="int64")
        faiss.normalize_L2(vectors)             # unit length -> inner product == cosine similarity

        with self._lock:
            if self.index is None:
                self.index = faiss.IndexIDMap(faiss.IndexFlatIP(vectors.shape[1]))
            elif vectors.shape[1] != self.index.d:
                raise ValueError(
                    f"Embedding size changed ({vectors.shape[1]} vs {self.index.d} in the index). "
                    "You switched embedding models: delete backend/storage/ and re-upload your files."
                )
            self.index.remove_ids(id_array)     # "upsert": never leave two vectors under one id
            self.index.add_with_ids(vectors, id_array)
            self._save()

    def remove(self, ids: Sequence[int]) -> int:
        if len(ids) == 0:
            return 0
        with self._lock:
            if self.index is None:
                return 0
            removed = int(self.index.remove_ids(np.asarray(ids, dtype="int64")))
            if removed:
                self._save()
            return removed

    # read
    def search(
        self, query: np.ndarray, k: int, allowed_ids: Optional[Collection[int]] = None
    ) -> List[Tuple[int, float]]:
        """Return up to k (chunk_id, cosine_similarity) pairs, best first.

        If `allowed_ids` is given, FAISS only considers those ids (filter BEFORE ranking).
        """
        with self._lock:
            if self.index is None or self.index.ntotal == 0:
                return []
            if allowed_ids is not None and len(allowed_ids) == 0:
                return []
            q = np.array(query, dtype="float32").reshape(1, -1)
            if q.shape[1] != self.index.d:
                raise ValueError("Query vector size does not match the index.")
            faiss.normalize_L2(q)
            params = None
            selector = None
            if allowed_ids is not None:
                selector = faiss.IDSelectorBatch(np.array(sorted(allowed_ids), dtype="int64"))
                params = faiss.SearchParameters()
                params.sel = selector
            scores, ids = self.index.search(q, min(k, self.index.ntotal), params=params)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]

    # self-repair
    def reconcile(self, valid_ids: Set[int]) -> Tuple[int, int]:
        """Drop vectors whose chunk no longer exists. Returns (strays_removed, chunks_missing_a_vector)."""
        present = self.all_ids()
        strays = present - valid_ids
        if strays:
            self.remove(sorted(strays))
        return len(strays), len(valid_ids - present)

vector_store = VectorStore()