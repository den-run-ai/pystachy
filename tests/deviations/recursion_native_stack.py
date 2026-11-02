# Documented deviation (docs/language/compatibility.md#errors-and-control-flow, #1015): native
# frames live on the thread's stack, so a recursion that the stack cannot hold raises
# RecursionError below sys.getrecursionlimit(), when the stack pointer reaches the native stack's
# floor (a margin above its end), where CPython, whose Python frames live on the heap, completes.
# The error is catchable, and finally blocks and stdout written before it survive; uncaught, it
# ends the program with status 1. This assumes a stack of at most 16 MiB (ulimit -s; 8 MiB
# is usual): 700,000 of climb's frames need twice that (tools/test_stack_floor.py pins the
# behaviour under a fixed ulimit -s).
import sys

seen: list[float] = [0.0]


def climb(n: int, a: float, b: float, c: float, d: float) -> float:
    # (work after the call keeps every frame on the stack, and the floats live across it)
    if n == 0:
        return 0.0
    r = climb(n - 1, a + 1.0, b + 2.0, c + 3.0, d + 4.0)
    seen[0] = r
    return r + a + b + c + d


sys.setrecursionlimit(2000000)
print("output before the recursion is kept")
try:
    print(climb(700000, 0.0, 0.0, 0.0, 0.0))
except RecursionError as e:
    print("RecursionError:", e)
finally:
    print("finally")
print(sys.getrecursionlimit(), climb(10, 0.0, 0.0, 0.0, 0.0))
print(climb(700000, 0.0, 0.0, 0.0, 0.0))
