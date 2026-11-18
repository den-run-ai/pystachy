# A comprehension's variable spelled as the sentinel is not the sentinel: a sentinel parameter's
# test of it reads that object at run time, as CPython's does
S = object()


def f(x: int = S) -> list[bool]:
    return [True if x is S else False for S in [object()]]


def h(x: int = S) -> bool:
    return True if x is S else False


print(f(), h(), h(3))
