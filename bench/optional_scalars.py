# Optional minima: a direct numeric scan and a rank-lookup shape used by BPE.
# `python3 bench/optional_scalars.py [direct|ranks] [rounds]` prints a checksum.
# Compare AOT builds with the same source and -unionslots to isolate the pass;
# this is a representation microbenchmark, not an end-to-end tokenizer workload.
import sys


def direct_minimum(xs: list[int], rounds: int) -> int:
    total = 0
    for _ in range(rounds):
        best: int | None = None
        for x in xs:
            if best is None or x < best:
                best = x
        total += 13 if best is None else best
    return total


def rank_minimum(keys: list[int], ranks: dict[int, int], rounds: int) -> int:
    total = 0
    for _ in range(rounds):
        best: int | None = None
        position: int | None = None
        i = 0
        for key in keys:
            rank = ranks.get(key)
            if rank is not None and (best is None or rank < best):
                best = rank
                position = i
            i += 1
        total += 13 if best is None else best
        total += 17 if position is None else position
    return total


mode = sys.argv[1] if len(sys.argv) > 1 else "ranks"
rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 32
if mode == "direct":
    xs = list(range(320, 0, -1))
    print(direct_minimum(xs, rounds))
else:
    keys = list(range(320))
    ranks = {i: 320 - i for i in range(320) if i % 5 != 0}
    print(rank_minimum(keys, ranks, rounds))
