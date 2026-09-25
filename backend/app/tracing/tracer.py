import time
from contextlib import contextmanager
from typing import Dict

class Tracer:
    """Times each stage of the pipeline, so the response can report where the time went."""

    def __init__(self):
        self.stages: Dict[str, float] = {}

    @contextmanager
    def stage(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = round((time.perf_counter() - start) * 1000, 1)

    def as_dict(self) -> dict:
        return {"stages_ms": self.stages, "total_ms": round(sum(self.stages.values()), 1)}