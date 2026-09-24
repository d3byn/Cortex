from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[int]], k: int = 60
) -> List[Tuple[int, float]]:
    """Merge several best-first lists of ids into one. Returns [(id, fused_score)], best first.

    score(id) = sum over every list containing it of 1 / (k + rank),  rank starting at 1.
    """
    scores: Dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)