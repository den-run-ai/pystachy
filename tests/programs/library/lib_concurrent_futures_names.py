# Naming a future's type: Future[int], Future[None] and Future[str | None] in the annotations
# of parameters, variables and fields, the bare Future of a function that takes any, and an
# executor as a field. A call that returns None gives a Future[None]
from concurrent.futures import Future, ThreadPoolExecutor, wait


def load(url: str, timeout: int) -> int:
    return len(url) * timeout


def tail(url: str) -> str | None:
    return url[7:] or None


def touch(seen: list[str], url: str) -> None:
    seen.append(url)


def first_result(fut: Future[int]) -> int:
    return fut.result()


def total(futs: list[Future[int]]) -> int:
    return sum(f.result() for f in futs)


def is_done(fut: Future) -> bool:
    return fut.done()


def maybe(fut: "Future[str | None]") -> str:
    r = fut.result()
    return "nothing" if r is None else r


class Downloader:
    def __init__(self, workers: int) -> None:
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.pending: list[Future[int]] = []
        self.last: Future[int] | None = None
        self.touched: Future[None] | None = None
        self.seen: list[str] = []

    def add(self, url: str) -> None:
        self.last = self.pool.submit(load, url, 2)
        self.pending.append(self.last)
        self.touched = self.pool.submit(touch, self.seen, url)

    def finish(self) -> list[int]:
        self.pool.shutdown()
        return [f.result() for f in self.pending]


URLS = ["http://a", "http://bb", "http://"]
with ThreadPoolExecutor(max_workers=5) as executor:
    fs: list[Future[int]] = []
    for u in URLS:
        fs.append(executor.submit(load, u, 1))
    wait(fs)
    print(first_result(fs[0]), total(fs), is_done(fs[1]))
    seen: list[str] = []
    nothing: list[Future[None]] = [executor.submit(touch, seen, "x")]
    made = Future[None]()
    made.set_result(None)
    nothing.append(made)
    print([f.result() for f in nothing], seen, is_done(nothing[0]))
    tails = [executor.submit(tail, u) for u in URLS]
    print([maybe(f) for f in tails])
d = Downloader(2)
for u in URLS:
    d.add(u)
print(d.finish(), sorted(d.seen))
last = d.last
touched = d.touched
if last is not None and touched is not None:
    print(last.result(), touched.result(), last is d.pending[-1])
