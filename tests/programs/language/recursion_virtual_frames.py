# A call through a base of more than eight concrete classes selects its override in a shared
# function (Gen.dispatch_call), which only forwards to the override and counts no frame, as a
# Callable's adapter does not (recursion_callable_frames.py): recursions that CPython completes
# near the limit complete, and an unbounded one is caught.
import sys


class Step:
    def down(self, n: int) -> int:
        return -n


class S0(Step):
    def down(self, n: int) -> int:
        if n == 0:
            return 0
        return chain[n % len(chain)].down(n - 1) + 1


class S1(S0):
    pass


class S2(S0):
    pass


class S3(S0):
    pass


class S4(S0):
    pass


class S5(S0):
    pass


class S6(S0):
    pass


class S7(S0):
    pass


class S8(S0):
    pass


class S9(S0):
    pass


chain: list[Step] = [S0(), S1(), S2(), S3(), S4(), S5(), S6(), S7(), S8(), S9()]
original = sys.getrecursionlimit()
sys.setrecursionlimit(100)
for depth in (10, 90):
    print(depth, chain[0].down(depth), chain[7].down(depth), Step().down(depth))
try:
    print(chain[0].down(500))
except RecursionError:
    print("caught")
print(chain[3].down(90))
sys.setrecursionlimit(original)
print(sys.getrecursionlimit() == original)
