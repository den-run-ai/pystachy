# isinstance() with type(None) and object in a template: decided by the argument's type, or by
# whether an optional value or an object is None


class C:
    def __init__(self, v: int) -> None:
        self.v = v


def kind(x):
    if isinstance(x, type(None)):
        return "none"
    if isinstance(x, (str, type(None))):
        return "str"
    return "other"


def tests(x):
    return [isinstance(x, object), isinstance(x, type(None)), isinstance(x, (type(None), int)),
            isinstance(x, int | None), isinstance(x, (C, type(None))), isinstance(x, float | None)]


def value(x):
    if not isinstance(x, type(None)):
        return x
    return 0


def name(n: int) -> str | None:
    return "s" if n > 0 else None


def num(n: int) -> int | None:
    return n if n > 0 else None


def obj(n: int) -> C | None:
    return C(n) if n > 0 else None


print(kind(None), kind(1), kind("a"), kind(name(1)), kind(name(0)), kind(num(0)), kind(num(2)),
      kind(obj(0)), kind(obj(1)), kind(C(1)), kind([1]), kind(1.5))
print(tests(None), tests(1), tests("a"))
print(tests(name(0)), tests(num(0)), tests(num(4)))
print(tests(obj(0)), tests(obj(3)), tests(C(3)), tests(2.0))
print(value(5), value(None))
