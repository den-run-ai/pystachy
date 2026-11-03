# Unbounded recursion under a raised sys.setrecursionlimit() (#1015): where the native stack
# cannot hold the limit's depth (an 8 MiB stack holds about 170,000 of climb's frames), the
# stack's floor raises RecursionError before the stack runs out, with ordinary except, finally and
# re-raise handling; a larger stack reaches the logical limit first, as CPython does. Each
# recursion here raises either way, and nothing printed depends on which bound did. Nothing
# allocates while the stack is deep (each collection scans the whole stack).
import sys
from collections.abc import Callable

entered: list[int] = [0]
finished: list[int] = [0]
relayed: list[int] = [0]
seen: list[float] = [0.0]
hops: list[Callable[[int], int]] = []


def climb(n: int, a: float, b: float, c: float, d: float) -> float:
    # (work after the call keeps every frame on the stack, and the floats live across it)
    if n == 100000000:
        return 0.0
    r = climb(n + 1, a + 1.0, b + 2.0, c + 3.0, d + 4.0)
    seen[0] = r
    return r + a + b + c + d


def nested(n: int) -> int:
    entered[0] += 1
    try:
        if n == 100000000:
            return 0
        return nested(n + 1) + 1
    finally:
        finished[0] += 1


def relay(n: int) -> int:
    try:
        if n == 100000000:
            return 0
        return relay(n + 1) * 2 + 1
    except RecursionError:
        relayed[0] += 1
        raise


def hop(n: int) -> int:
    # (through a function value: the entry keeps the depth word, unlike climb's closed recursion)
    if n == 100000000:
        return 0
    r = hops[0](n + 1)
    entered[0] = r
    return r + 1


def fact(n: int) -> int:
    return 1 if n <= 1 else n * fact(n - 1)


hops.append(hop)
sys.setrecursionlimit(300000)
print("output before the recursion is kept")
for attempt in range(2):
    try:
        print(climb(0, 0.0, 0.0, 0.0, 0.0))
    except RecursionError:
        print("climb: caught", attempt)
    finally:
        print("climb: finally", attempt)
try:
    print(nested(0))
except RecursionError:
    print("nested: every finally ran", entered[0] == finished[0], entered[0] > 1000)
try:
    print(relay(0))
except RecursionError:
    print("relay: re-raised", relayed[0] > 1000)
try:
    print(hop(0))
except RecursionError:
    print("hop: caught")
print(sys.getrecursionlimit(), fact(20))
