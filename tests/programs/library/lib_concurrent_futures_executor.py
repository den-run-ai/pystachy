# Executor as a type and as a base class: a function that takes any Executor calls the
# submit() of the executor it is given, and a subclass that defines submit() inherits map(),
# shutdown() and the context manager; Executor's own submit() raises NotImplementedError
from concurrent.futures import Executor, Future, ThreadPoolExecutor


class Inline(Executor):
    def __init__(self) -> None:
        self.calls = 0

    def submit(self, fn, /, *args, **kwargs):
        self.calls += 1
        f = Future[int]()
        f.set_result(fn(*args, **kwargs))
        return f


def scale(x: int) -> int:
    return x * 2


def run(pool: Executor, x: int) -> int:
    return pool.submit(scale, x).result()


with ThreadPoolExecutor(2) as pool:
    print(run(pool, 4))
with Inline() as ex:
    print(ex.submit(scale, 4).result(), list(ex.map(scale, [1, 2])), ex.calls)
try:
    Executor().submit(scale, 1)
except NotImplementedError:
    print("NotImplementedError")
