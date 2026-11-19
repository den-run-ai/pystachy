# A Sequence[T] parameter's empty tuple default, (), in a function that only reads the
# parameter's items: an empty list[T], which nothing the function does can tell from ()
from collections.abc import Sequence
import typing


def format_func(name: str, errors: Sequence[tuple[int, str]] = ()) -> list[str]:
    lines = [name]
    for line, msg in errors:
        lines.append(f"{line}: {msg}")
    return lines


def summary(xs: typing.Sequence[int] = ()) -> str:
    if not xs:
        return "empty"
    total = sum(xs)
    big = [x for x in xs if x > 2]
    pairs = list(enumerate(xs))
    return f"{len(xs)} total={total} big={big} {pairs} has3={3 in xs} no9={9 not in xs} {min(xs)} {max(xs)} {sorted(xs)}"


def count(words: "Sequence[str]" = (), *, extra: int = 0) -> int:
    n = extra
    while words and n < 0:
        n += 1
    for i, w in zip(range(10), words):
        n += i + len(w)
    return n + (1 if any(w == "a" for w in words) else 0) + (2 if all(words) else 0)


print(format_func("f"))
print(format_func("g", [(1, "bad"), (2, "worse")]))
print(summary(), summary([5, 1, 3]))
print(count(), count(["a", "bc"]), count(extra=-2))
