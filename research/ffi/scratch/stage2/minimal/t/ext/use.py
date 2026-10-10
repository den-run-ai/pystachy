import sys, threading
import fastmath
assert fastmath.__file__.endswith(".so"), fastmath.__file__
import fastmath as m
print("fib(90) =", m.fib(90))
print("check(4) =", m.check(4))
for bad in [lambda: m.check(-5), lambda: m.fib(2**64), lambda: m.fib("x"), lambda: m.bye(3), lambda: m.fib(93)]:
    try:
        bad()
    except (ValueError, OverflowError, TypeError, SystemExit) as e:
        print("caught", type(e).__name__, e)
print(m.shout("héllo wörld"), m.words("a b a c b a" * 1000))
print("python before")
m.hello("CPython")
print("python after")
t = []
th = threading.Thread(target=lambda: t.append(m.ncalls) and None)
def other():
    try:
        m.ncalls()
    except RuntimeError as e:
        t.append(str(e)[:40])
th = threading.Thread(target=other); th.start(); th.join()
print("from another thread:", t)
print("calls:", m.ncalls())
