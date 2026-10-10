import time
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
def inc(n: int) -> int:
    return n + 1
N = 1_000_000
t0 = time.perf_counter()
for i in range(N):
    inc(i)
t1 = time.perf_counter()
print(f"CPython inc (py function): {(t1-t0)/N*1e9:.1f} ns/call")
t0 = time.perf_counter()
for _ in range(3):
    r = fib(25)
t1 = time.perf_counter()
print(f"CPython fib(25)={r}: {(t1-t0)/3*1e3:.3f} ms")
t0 = time.perf_counter()
for i in range(N):
    pass
t1 = time.perf_counter()
print(f"empty loop: {(t1-t0)/N*1e9:.1f} ns/iter")
