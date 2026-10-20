# Builtins and builtin methods that take an optional value: print's sep= and end= (None is
# the default), sum() with a start, writelines() and join() of str | None items
import sys


def get(c: bool, s: str) -> str | None:
    return s if c else None


def nums(c: bool) -> list[int] | None:
    return [1, 2] if c else None


def lines(c: bool) -> list[str] | None:
    return ["x\n", "y\n"] if c else None


print("a", "b", sep=get(False, "-"), end=get(False, "!"))
print("|")
print("a", "b", sep=get(True, "-"), end=get(True, "!"))
print("|")
print(sum(nums(True), 10), sum(nums(True)))
sys.stdout.writelines(lines(True))
xs: list[str | None] = ["a", "b"]
print(",".join(xs), int(get(True, "12"), 8))
