# Documented deviation: a future that is not done can only be finished by the program's one
# thread (lib/compatibility.md#concurrentfutures), so a wait for it without a timeout, by
# result(), exception(), wait() or as_completed(), raises RuntimeError where CPython waits for
# another thread to finish it. Under CPython, a thread finishes each future here: this prints
# 1, ValueError, 1 and [4]
import _thread
import time
from concurrent.futures import Future, as_completed, wait

a = Future[int]()
b = Future[int]()
c = Future[int]()
d = Future[int]()


def later() -> None:
    time.sleep(0.2)
    a.set_result(1)
    time.sleep(0.2)
    b.set_exception(ValueError("b"))
    time.sleep(0.2)
    c.set_result(3)
    time.sleep(0.2)
    d.set_result(4)


try:
    _thread.start_new_thread(later, ())
except NotImplementedError:
    print("no thread")
for k in range(4):
    try:
        if k == 0:
            print(a.result())
        elif k == 1:
            print(type(b.exception()).__name__)
        elif k == 2:
            print(len(wait([c]).done))
        else:
            print([f.result() for f in as_completed([d])])
    except RuntimeError as e:
        print("RuntimeError:", e)
