# Documented deviation: a Pystachy program runs one thread, so ThreadPoolExecutor.submit() runs
# the call itself, before it returns (lib/compatibility.md#concurrentfutures). A call that waits
# for the thread that submitted it, here for a lock that thread holds, cannot finish: the lock's
# acquire() raises _thread's RuntimeError, which the future keeps. Under CPython a worker thread
# runs the call and waits until the lock is released: this prints False, done, ['main', 'task']
import _thread
from concurrent.futures import ThreadPoolExecutor

gate = _thread.allocate_lock()
order: list[str] = []


def task() -> str:
    with gate:
        order.append("task")
    return "done"


with ThreadPoolExecutor(max_workers=1) as pool:
    gate.acquire()
    fut = pool.submit(task)
    print(fut.done())
    order.append("main")
    gate.release()
    try:
        print(fut.result())
    except RuntimeError as e:
        print("RuntimeError:", e)
print(order)
