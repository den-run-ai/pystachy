# A function compiled in the middle of another's compile is compiled as it would be on its own
# (#822): here make(int), which dry() compiles while it types x = make(3) for the read in
# x is None. Its walrus assigns m, as CPython's does (the instance is the one the call runs).
def make(n):
    m = 0
    if (m := n * 2) > 100:
        print("big")
    return m


def f():
    x = None
    if x is None:
        print("x is None")
    x = make(3)
    print(x)


f()
