# A caller keeps timers of different functions in one list and reads a timer's function,
# arguments and keyword arguments back: lib/threading.py holds them as Any values, the contract
# of its row in docs/dynamic-any-boundaries.md. One Timer class for every function could not give
# them back with their types, and a Timer class per function could not share the list
import threading


def f() -> None:
    print("f")


def g(n: int, tag: str = "t") -> None:
    print("g", n, tag)


timers = [threading.Timer(0.0, f), threading.Timer(0.0, g, args=(1,), kwargs={"tag": "k"})]
for t in timers:
    print(t.args, t.kwargs, t.interval, t.finished.is_set())
    t.cancel()
    t.run()
print([t.finished.is_set() for t in timers])
timer = threading.Timer(5.0, g, args=(2,))
print(timer.args, timer.kwargs, timer.interval, timer.function is g, timer.function is f)
n, = timer.args
print(n + 1, len(timers[1].kwargs), timers[1].kwargs["tag"].upper())
