# Odd exception classes: one named as a builtin exception (the program's own), an __init__ that
# lets self escape before super().__init__(), __eq__, a bare raise in a called function, and
# a template catching objects it was given.
class ValueError(Exception):
    pass


class Leaky(Exception):
    def __init__(self, n: int):
        self.n = n
        self.note = self.describe()
        super().__init__(n)

    def describe(self) -> str:
        return f"leaky {self.n}"


class Sub(Leaky):
    def __init__(self, n: int):
        super().__init__(n)
        self.extra = n * 2

    def __str__(self) -> str:
        return f"sub {self.extra} {self.note}"

    def __eq__(self, other: "Sub") -> bool:
        return self.n == other.n


def find(n: int) -> Sub | None:
    if n > 0:
        return Sub(n)
    return None


def again() -> None:
    raise


def generic(x, flag):
    try:
        if flag:
            raise x
        return "no"
    except Leaky as e:
        return f"generic {e.n}"


try:
    raise ValueError("mine")
except ValueError as e:
    print("own ValueError:", repr(e))
try:
    int("x")
except ValueError:
    print("never")
except Exception as e:
    print("builtin:", e)
s = Sub(3)
print(s, s == Sub(3), s == Sub(4), find(1), find(0))
d: dict[str, Leaky] = {"a": Leaky(1), "b": Sub(2)}
print(d)
try:
    try:
        raise Sub(5)
    except Leaky:
        again()
except Sub as e:
    print("again:", e)
try:
    raise Sub(6) from Leaky(7)
except Leaky as e:
    print(repr(e), e.note)
print(generic(Sub(8), True), generic(Leaky(9), False))
try:
    raise Leaky(1)
except (Leaky, KeyError) as e:
    print("mixed:", repr(e), type(e).__name__)
raise ValueError("uncaught own")
