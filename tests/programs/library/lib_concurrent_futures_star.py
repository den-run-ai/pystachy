# from concurrent.futures import *: the names of __all__ that the port has
from concurrent.futures import *


def scale(x: int) -> int:
    return x * 2


pool = ThreadPoolExecutor(2)
f = pool.submit(scale, 2)
print(wait([f]).done == {f}, f.result(), [g.result() for g in as_completed([f])])
print(FIRST_COMPLETED, FIRST_EXCEPTION, ALL_COMPLETED)
print(issubclass(InvalidStateError, Exception), issubclass(CancelledError, Exception))
print(issubclass(BrokenExecutor, RuntimeError), TimeoutError.__name__)
print(isinstance(pool, Executor), isinstance(f, Future))
pool.shutdown()
