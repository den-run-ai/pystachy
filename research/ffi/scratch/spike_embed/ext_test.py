import sys, time, threading
sys.path.insert(0, sys.argv[1])
t = time.perf_counter()
import pysext
print("import ms", round((time.perf_counter() - t) * 1000, 2))
print("fib(50) =", pysext.fib(50))
try:
    pysext.fib(100)
except OverflowError as e:
    print("OverflowError from Pystachy:", e)
try:
    pysext.boom(7)
except ValueError as e:
    print("ValueError from Pystachy:", e)
g = [pysext.greet(i % 300) for i in range(3000)]
print("greet ok:", all(x == "".join(str(j) + "," for j in range(i % 300)) for i, x in enumerate(g)))
t = time.perf_counter()
for i in range(100000):
    pysext.fib(20)
print("100k calls fib(20): ms", round((time.perf_counter() - t) * 1000, 1))
def fibpy(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
t = time.perf_counter()
for i in range(100000):
    fibpy(20)
print("100k calls CPython fibpy(20): ms", round((time.perf_counter() - t) * 1000, 1))
r = []
th = threading.Thread(target=lambda: r.append(pysext.greet(3)) if False else None)
def other():
    try:
        pysext.greet(3)
    except RuntimeError as e:
        r.append(str(e))
th = threading.Thread(target=other); th.start(); th.join()
print("from another thread:", r)
