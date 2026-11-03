# Documented deviation: a Pystachy program runs one thread (lib/_pystachy_thread.py), so
# threading.Thread.start() raises _thread's NotImplementedError, where CPython runs the thread's
# run() in a new thread (here printing "run worker")
import threading


class Worker(threading.Thread):
    def run(self) -> None:
        print("run", self.name)


w = Worker(name="worker")
try:
    w.start()
    w.join()
except NotImplementedError as e:
    print("NotImplementedError:", e)
print(w.is_alive())
