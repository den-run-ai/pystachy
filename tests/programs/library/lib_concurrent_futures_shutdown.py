# An executor's life: max_workers must be positive, shutdown() may be called again, with wait
# and cancel_futures, and after it submit() and map() raise RuntimeError; a with statement shuts
# the executor down, also where its block raises. The module's exception classes
import concurrent.futures
import concurrent.futures.thread
from concurrent.futures import BrokenExecutor, Executor, ThreadPoolExecutor
from concurrent.futures.thread import BrokenThreadPool


def twice(n: int) -> int:
    return 2 * n


for workers in [0, -3]:
    try:
        ThreadPoolExecutor(max_workers=workers)
    except ValueError as e:
        print("ValueError:", e)
pool = ThreadPoolExecutor(3, "worker")
f = pool.submit(twice, 4)
pool.shutdown(wait=False)
print(f.result())
pool.shutdown()
pool.shutdown(True, cancel_futures=True)
try:
    pool.submit(twice, 5)
except RuntimeError as e:
    print("RuntimeError:", e)
try:
    pool.map(twice, [1, 2])
except RuntimeError as e:
    print("RuntimeError:", e)
with ThreadPoolExecutor() as ex:
    g = ex.submit(twice, 6)
    print(isinstance(ex, Executor), isinstance(ex, ThreadPoolExecutor))
print(g.result(), g.done())
try:
    ex.submit(twice, 7)
except RuntimeError as e:
    print("RuntimeError:", e)
try:
    with ThreadPoolExecutor(max_workers=1) as ex2:
        h = ex2.submit(twice, 8)
        raise KeyError("in the block")
except KeyError as e:
    print("KeyError:", e, h.result())
print(issubclass(BrokenThreadPool, BrokenExecutor), issubclass(BrokenExecutor, RuntimeError))
print(issubclass(concurrent.futures.CancelledError, Exception))
print(concurrent.futures.TimeoutError is TimeoutError)
print(issubclass(concurrent.futures.InvalidStateError, concurrent.futures._base.Error))
try:
    raise BrokenThreadPool("broken")
except BrokenExecutor as e:
    print("BrokenExecutor:", e)
try:
    raise concurrent.futures.thread.BrokenThreadPool("pool")
except RuntimeError as e:
    print("RuntimeError:", e)
print("ThreadPoolExecutor" in concurrent.futures.__all__, "wait" in concurrent.futures.__all__)
