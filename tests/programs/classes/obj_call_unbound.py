# o(args) reads variable o first: a global, a local or a field the call may find unassigned raises
# CPython's NameError, UnboundLocalError or AttributeError, as reading it does (a global also where
# the call is compiled before the assignment that types it); self(...) in __init__ lets __call__
# see the fields not yet assigned.
class Scale:
    def __init__(self, k: int) -> None:
        self.k = k

    def __call__(self, x: int) -> int:
        return x * self.k


class Early:
    def __init__(self) -> None:
        self.v: int = self(1)
        self.k = 2

    def __call__(self, x: int) -> int:
        return x + self.k


def run() -> int:
    return tripler(2)


def local(flag: bool) -> int:
    if flag:
        g = Scale(2)
    return g(3)


def lookup(x):
    return quad(x)


try:
    print(run())
except NameError as e:
    print("NameError:", e)
try:
    print(quad(1))
except NameError as e:
    print("NameError:", e)
try:
    print(lookup(2))
except NameError as e:
    print("NameError:", e)
quad = Scale(4)
print(quad(1), lookup(2))
tripler = Scale(3)
print(run(), local(True))
try:
    print(local(False))
except UnboundLocalError as e:
    print("UnboundLocalError:", e)
try:
    print(Early().v)
except AttributeError as e:
    print("AttributeError:", e)
del tripler
print(tripler(1))
