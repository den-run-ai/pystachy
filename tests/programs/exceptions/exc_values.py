# Builtin exceptions as values: annotated as Exception, BaseException or any builtin exception
# class, kept in variables, containers and fields, passed, returned and raised again.
import sys


class Report:
    def __init__(self, name: str):
        self.name = name
        self.errors: list[Exception] = []
        self.last: BaseException = ValueError("none yet")

    def add(self, e: Exception) -> None:
        self.errors.append(e)
        self.last = e


def parse(s: str) -> int:
    return int(s)


def failure(s: str) -> ValueError:
    try:
        parse(s)
    except ValueError as e:
        return e
    return ValueError("no failure")


def pick(errs: list[Exception], i: int) -> Exception:
    return errs[i]


r = Report("inputs")
for s in ["1", "x", "2", "", "y7"]:
    try:
        print(parse(s))
    except ValueError as e:
        r.add(e)
print(len(r.errors), r.errors)
print(repr(r.last), str(r.last))
print([str(e) for e in r.errors])
f = failure("abc")
print(f"{f} | {f!r} | {f!s:>3}")
print("%s | %r" % (f, f), "%s" % f)
errs: list[BaseException] = [KeyError("k"), IndexError("list index out of range"), OSError("disk"), ZeroDivisionError()]
print(errs)
table: dict[str, Exception] = {"key": KeyError("k"), "val": ValueError(3)}
print(table)
print(table["val"], repr(table["key"]))
pair: tuple[str, Exception] = ("x", RuntimeError("boom", 2))
print(pair)
a = ValueError("same")
b = ValueError("same")
print(a == a, a == b, a is a, a is b, a != b, a in [b], a in [a, b], [a].index(a))
try:
    print(sorted([ValueError("b"), ValueError("a")]))
except TypeError as e:
    print("TypeError:", e)
try:
    print(r.errors[0] < r.errors[1])
except TypeError as e:
    print("TypeError:", e)
for i in range(3):
    try:
        raise pick(r.errors, i)
    except ValueError as e:
        print("again:", e)
try:
    raise r.last
except Exception as e:
    print("last:", repr(e))
try:
    try:
        d: dict[str, int] = {}
        print(d["missing"])
    except KeyError as e:
        raise RuntimeError("lookup failed") from e
except RuntimeError as e:
    print(repr(e))
try:
    raise ValueError("chained") from failure("q")
except ValueError as e:
    print(e)
try:
    raise SystemExit(None)
except SystemExit as e:
    print(repr(e), repr(str(e)))
try:
    sys.exit(None)
except SystemExit as e:
    print(repr(e), repr(str(e)))
holder: list[Exception] = []
try:
    print([1, 2][5])
except IndexError as e:
    holder.append(e)
print(holder[0], len(holder))
raise holder[0]
