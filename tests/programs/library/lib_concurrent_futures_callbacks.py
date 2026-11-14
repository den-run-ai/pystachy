# add_done_callback(): a callback added to a finished future is called at once, with the future,
# whatever it returns; one that raises an Exception is reported on stderr (as logging reports it
# where the program configures none: its last line is the exception's) and the next ones run.
# The futures are finished before a callback is added, so that the calling thread calls it
from concurrent.futures import Future, ThreadPoolExecutor


class CallbackError(Exception):
    pass


class Collector:
    def __init__(self) -> None:
        self.got: list[int] = []

    def take(self, f: Future[int]) -> None:
        self.got.append(f.result())


def good(f: Future[int]) -> None:
    print("good", f.result(), f.done())


def answer(f) -> str:
    print("answer", f.result())
    return "ignored"


def failed(f: Future[int]) -> None:
    print("failed", type(f.exception()).__name__)


def bad(f: Future[int]) -> None:
    raise CallbackError("in a callback")


def div(a: int, b: int) -> int:
    return a // b


collector = Collector()
with ThreadPoolExecutor(max_workers=2) as pool:
    fut = pool.submit(div, 7, 2)
    err = pool.submit(div, 7, 0)
fut.add_done_callback(good)
fut.add_done_callback(answer)
fut.add_done_callback(collector.take)
fut.add_done_callback(lambda f: print("lambda", f.result() + 1))
err.add_done_callback(failed)
print(collector.got)
fut.add_done_callback(bad)
fut.add_done_callback(good)

made = Future[int]()
made.add_done_callback(good)
made.add_done_callback(bad)
made.add_done_callback(collector.take)
print("pending", collector.got)
made.set_result(9)
print(collector.got)
