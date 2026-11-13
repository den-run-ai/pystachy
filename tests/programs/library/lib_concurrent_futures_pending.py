# The waits for futures that are not done, with a timeout: result() and exception() raise
# TimeoutError, wait() returns them in not_done and as_completed() raises TimeoutError with its
# count. Only the program's own code finishes these futures, in its one thread, also between two
# of as_completed()'s yields, which then come in the order the futures finished in. A cancelled
# future counts as done for wait() once set_running_or_notify_cancel() has noticed it
from concurrent.futures import (ALL_COMPLETED, FIRST_COMPLETED, FIRST_EXCEPTION, Future,
                                TimeoutError, as_completed, wait)

a = Future[int]()
b: Future[int] = Future()
c = Future[int]()
try:
    a.result(timeout=0.01)
except TimeoutError:
    print("result: TimeoutError")
try:
    a.exception(0)
except TimeoutError:
    print("exception: TimeoutError")
r = wait([a, b], timeout=0.01)
print(len(r.done), len(r.not_done))
r = wait([a, b], timeout=0, return_when=FIRST_COMPLETED)
print(len(r.done), len(r.not_done))
r = wait([a, b], timeout=-1)
print(len(r.done), len(r.not_done))
try:
    for f in as_completed([a, b], timeout=0.01):
        print("unexpected")
except TimeoutError as e:
    print("as_completed: TimeoutError:", e)
try:
    wait([a], timeout=0, return_when="LATER")
except ValueError as e:
    print("ValueError:", e)
a.set_result(1)
r = wait([a, b, c], timeout=0, return_when=FIRST_COMPLETED)
print(len(r.done), len(r.not_done), a in r.done, b in r.not_done)
r = wait([a, b, c], timeout=0.01, return_when=FIRST_EXCEPTION)
print(len(r.done), len(r.not_done))
r = wait([a, b, c], timeout=0.01, return_when=ALL_COMPLETED)
print(len(r.done), len(r.not_done))
got = []
try:
    for f in as_completed([a, b, c, a], timeout=0.05):
        got.append(f.result())
        if f is a:
            b.set_result(2)
except TimeoutError as e:
    print("as_completed: TimeoutError:", e)
print(got)
c.set_exception(ZeroDivisionError("zero"))
r = wait([a, b, c], return_when=FIRST_EXCEPTION)
print(len(r.done), len(r.not_done), [type(f.exception()).__name__ for f in [a, b, c]])

d = Future[int]()
print(d.cancel())
r = wait([d], timeout=0.01)
print(len(r.done), len(r.not_done), d.done())
print(d.set_running_or_notify_cancel())
r = wait([d])
print(len(r.done), len(r.not_done), [f.cancelled() for f in as_completed([d])])

# the futures that finish between two yields come in the order they finished in
p, q, u, v = Future[int](), Future[int](), Future[int](), Future[int]()
u.set_result(3)
order = []
for f in as_completed([p, q, u, v]):
    order.append(-1 if f.cancelled() else f.result())
    if f is u:
        q.set_result(2)
        v.cancel()
        v.set_running_or_notify_cancel()
        p.set_result(1)
print(order)
