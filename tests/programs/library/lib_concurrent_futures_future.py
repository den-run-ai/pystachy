# A Future that the program makes itself, of a named result type: its states (pending, running,
# cancelled, finished), cancel(), set_running_or_notify_cancel(), set_result(), set_exception(),
# their InvalidStateError, CancelledError, and its repr; the callbacks added while it is pending
# run in the order added when it finishes or is cancelled, a callback added after that at once
from concurrent.futures import CancelledError, Future, InvalidStateError
import concurrent.futures


def show(tag: str, f: Future[int]) -> None:
    r = repr(f)
    print(tag, f.done(), f.running(), f.cancelled(), r[:11], r[r.index(" state="):])


events: list[str] = []


def first(f: Future[int]) -> None:
    events.append("first")


def second(f) -> int:
    events.append("second:%d" % f.result())
    return 1


f = Future[int]()
show("new", f)
f.add_done_callback(first)
f.add_done_callback(second)
f.add_done_callback(lambda fut: events.append("lambda"))
print(events)
print(f.set_running_or_notify_cancel(), f.cancel())
show("running", f)
f.set_result(5)
show("finished", f)
print(events, f.result(), f.exception(), f.cancel())
f.add_done_callback(first)
print(events)
try:
    f.set_result(6)
except InvalidStateError as e:
    msg = str(e)
    print("InvalidStateError:", msg[:21], msg[msg.index(" state="):])
try:
    f.set_exception(ValueError("late"))
except InvalidStateError:
    print("InvalidStateError")

c: Future[int] = Future()
c.add_done_callback(lambda fut: events.append("cancelled" if fut.cancelled() else "not"))
print(c.cancel(), c.cancel(), events[-1])
show("cancelled", c)
try:
    c.result()
except CancelledError:
    print("CancelledError")
try:
    c.exception()
except concurrent.futures.CancelledError as e:
    print("CancelledError", isinstance(e, concurrent.futures._base.Error), isinstance(e, Exception))
print(c.set_running_or_notify_cancel())
show("notified", c)
try:
    c.set_result(1)
except InvalidStateError as e:
    print("InvalidStateError:", str(e)[:23])

x = Future[int]()
x.set_exception(KeyError("k"))
show("raised", x)
try:
    x.result()
except KeyError as e:
    print("KeyError:", e, x.exception() is e)

n = Future[None]()
n.set_result(None)
print(n.result(), repr(n)[-18:])
s: Future[str | None] = Future()
s.set_result(None)
t = Future[list[int]]()
t.set_result([1, 2])
print(s.result(), repr(s)[-18:], t.result(), repr(t)[-14:])
