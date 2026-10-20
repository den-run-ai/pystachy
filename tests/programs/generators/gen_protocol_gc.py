# Suspended generators that hold what send() gave them (#490 stage 3): strings, lists, boxed ints
# and exception objects stay reachable through their frames while garbage is made and the
# collector runs (the GC-stress suites collect at every allocation).
from collections.abc import Generator


class Note(Exception):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


def keeper(k: int) -> Generator[int, list[str], str]:
    kept: list[list[str]] = []
    notes: list[str] = []
    try:
        while True:
            try:
                got = yield len(kept)
                if got is None:
                    break
                kept.append(got)
            except Note as n:
                notes.append(n.text)
    finally:
        print("keeper", k, "closing with", len(kept), "lists and", len(notes), "notes")
    return ",".join(kept[-1]) + "|" + ",".join(notes)


def summer() -> Generator[int, int | None, None]:
    total = 0
    while True:
        v = yield total
        if v is not None:
            total += v


gens = [keeper(i) for i in range(20)]
for g in gens:
    next(g)
sums = [summer() for _ in range(5)]
for s in sums:
    next(s)
for rnd in range(60):
    junk = [str(j) * 3 for j in range(50)]
    for i in range(len(gens)):
        gens[i].send([f"r{rnd}", f"g{i}", junk[i % 50]])
        if rnd % 15 == 0:
            gens[i].throw(Note(f"n{rnd}.{i}"))
    for s in sums:
        s.send(rnd)
results: list[str] = []
for g in gens[:3]:
    try:
        g.send(None)
    except StopIteration:
        results.append("stopped")
print(results)
for g in gens[3:]:
    g.close()
print([s.send(None) for s in sums])
print([next(g, -1) for g in gens[:5]])
