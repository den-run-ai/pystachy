# Suspended generators inside with blocks (#490 stage 4): the context managers they entered,
# @contextmanager's generators suspended at their yield, and what send() gave them stay
# reachable through the frames while garbage is made and the collector runs (the GC-stress
# suites collect at every allocation); closing, throwing into and finishing them then runs
# each manager's __exit__ in order.
from collections.abc import Generator, Iterator
from contextlib import contextmanager


class Ledger:
    def __init__(self, name: str) -> None:
        self.name = name
        self.lines: list[str] = []

    def __enter__(self) -> "Ledger":
        self.lines.append("open " + self.name)
        return self

    def __exit__(self, et, ev, tb) -> bool:
        self.lines.append("close " + self.name + (" " + et.__name__ if et is not None else ""))
        print("\n".join(self.lines))
        return et is not None and issubclass(et, KeyError)


@contextmanager
def scope(name: str) -> Iterator[list[str]]:
    kept = [name + str(i) for i in range(3)]
    try:
        yield kept
    finally:
        print("scope", name, ",".join(kept))


def worker(name: str) -> Generator[int, str, None]:
    with Ledger(name) as led, scope(name) as kept:
        while True:
            got = yield len(led.lines)
            if got is None:
                got = "-"
            led.lines.append(got * 2)
            kept.append(got)
            if got == "stop":
                return


def churn(n: int) -> int:
    junk: list[str] = []
    for i in range(n):
        junk.append(str(i) * (i % 7 + 1))
    return len(junk)


gens = [worker("w" + str(k)) for k in range(4)]
for g in gens:
    print(next(g))
for r in range(3):
    churn(200)
    for k in range(len(gens)):
        print(gens[k].send("r" + str(r) + "k" + str(k)))
churn(300)
gens[0].close()
try:
    gens[1].throw(KeyError("thrown"))
except StopIteration:
    print("w1 suppressed and finished")
try:
    gens[2].throw(ValueError("out"))
except ValueError as e:
    print("w2 raised", e)
try:
    gens[3].send("stop")
except StopIteration:
    print("w3 finished")
churn(100)
for g in gens:
    try:
        print(next(g))
    except StopIteration:
        print("finished")
