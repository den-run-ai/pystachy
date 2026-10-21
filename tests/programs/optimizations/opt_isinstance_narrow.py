# isinstance() narrows an optional local only where its result shows the value is not None:
# None is an object (issue #70), so isinstance(x, object) does not narrow x


def check(x: int | None) -> None:
    print(isinstance(x, object))


def obj(x: int | None) -> int:
    if isinstance(x, object):
        return x + 1  # x may be None here
    return 0


def notnone(x: str | None) -> str:
    if not isinstance(x, type(None)):
        return x.upper()
    return "-"


def early(x: list[int] | None) -> int:
    if isinstance(x, type(None)):
        return -1
    return len(x)


def other(x: int | None) -> int:
    if isinstance(x, str | None):
        return -1
    return x * 2  # neither a str nor None: an int


def both(x: float | None) -> float:
    while isinstance(x, (type(None), float)):
        return x + 0.5  # x may be None here
    return 0.0


def typed(x: dict[str, int] | None) -> int:
    if isinstance(x, dict):
        return len(x)
    return -1


check(None)
check(1)
print(obj(1), notnone(None), notnone("ab"), early(None), early([1, 2]), other(None), other(4), typed({"a": 1}), typed(None))
print(both(1.0))
try:
    print(both(None))
except TypeError as e:
    print("TypeError:", e)
print(obj(None))
