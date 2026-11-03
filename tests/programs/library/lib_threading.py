# lib/threading.py, CPython's threading on the one-thread _thread: locks, conditions, semaphores,
# events, barriers, timers and the main thread's Thread object behave as in CPython where no other
# thread runs (tests/deviations/threading_start.py: starting one)
import threading

lock = threading.RLock()
with lock:
    with lock:
        print("reentrant", lock._is_owned())
print(lock._is_owned(), lock.acquire(blocking=False), lock.acquire(timeout=0.01))
lock.release()
lock.release()
plain = threading.Lock()
print(plain.acquire(), plain.locked(), plain.acquire(blocking=False), plain.acquire(timeout=0.01))
plain.release()
print(plain.locked())
main = threading.current_thread()
print(main.name, main is threading.main_thread(), main.daemon, main.is_alive())
print(threading.get_ident() == main.ident, threading.get_native_id() == main.native_id)
print(threading.active_count(), [t.name for t in threading.enumerate()])
e = threading.Event()
print(e.is_set(), e.wait(0.01))
e.set()
print(e.is_set(), e.wait(0.01), e.wait())
e.clear()
print(e.is_set())
c = threading.Condition()
with c:
    c.notify()
    c.notify_all()
    print("wait", c.wait(0.01), c.wait_for(lambda: True))
cl = threading.Condition(threading.Lock())
with cl:
    print("plain wait", cl.wait(0.01))
s = threading.Semaphore(2)
print(s.acquire(), s.acquire(), s.acquire(blocking=False), s.acquire(timeout=0.01))
s.release(2)
with s:
    print("in semaphore")
b = threading.BoundedSemaphore(1)
with b:
    print("in bounded")
try:
    b.release()
except ValueError as err:
    print("ValueError:", err)
bar = threading.Barrier(1, action=lambda: print("action"))
print(bar.parties, bar.n_waiting, bar.broken, bar.wait())
bar.reset()
bar.abort()
print(bar.broken)
try:
    bar.wait()
except threading.BrokenBarrierError:
    print("BrokenBarrierError")


class Worker(threading.Thread):
    def __init__(self, n: int) -> None:
        super().__init__(name=f"worker-{n}", daemon=True)
        self.n = n

    def run(self) -> None:
        print("run", self.n, self.name, self.daemon)


w = Worker(3)
print(w.name, w.is_alive(), w.daemon, w.ident, w.native_id)
w.run()
w.name = "renamed"
print(w.name)
t = threading.Thread(target=lambda: print("target ran"))
print(t.name.startswith("Thread-"), t.daemon)
t.run()
t2 = threading.Thread(name="named")
t2.run()
print(t2.name)
timer = threading.Timer(0.01, lambda: print("timer fired"))
timer.cancel()
timer.run()
print(timer.finished.is_set())
loc = threading.local()
print(type(loc).__name__)
print(threading.TIMEOUT_MAX > 0, threading.stack_size())
try:
    threading.current_thread().join()
except RuntimeError as err:
    print("RuntimeError:", err)
print(repr(threading.main_thread()).startswith("<_MainThread(MainThread, started"))
