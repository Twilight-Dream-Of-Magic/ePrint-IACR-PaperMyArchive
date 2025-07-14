from __future__ import annotations

import random
from typing import List


def generate_seeded_indices(
    *,
    seed: int,
    count: int,
    state_count: int,
    unique: bool = False,
) -> List[int]:
    n = max(0, int(count))
    q = max(1, int(state_count))
    rng = random.Random(int(seed))
    if unique and n <= q:
        pool = list(range(q))
        rng.shuffle(pool)
        return [int(v) for v in pool[:n]]
    return [int(rng.randrange(q)) for _ in range(n)]

