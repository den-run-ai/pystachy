# "..." % (a, b), a literal format and a tuple display with only %s, %r and %a conversions, whose
# widths and precisions have at most two digits: CPython 3.11+ compiles it as an f-string, so each
# item is evaluated just before its conversion. Any other % evaluates every item first


class C:
    def __init__(self, n: str) -> None:
        self.n = n

    def __str__(self) -> str:
        print("str " + self.n)
        return self.n

    def __repr__(self) -> str:
        print("repr " + self.n)
        return "<" + self.n + ">"


class Bad:
    def __str__(self) -> str:
        print("str bad")
        raise ValueError("bad str")


def f(x: str) -> str:
    print("eval " + x)
    return x


def boom() -> str:
    print("eval boom")
    raise KeyError("boom")


FMT = "%s %s"

print("%s %s" % (C("a"), f("1")))
print("%r %s" % (C("b"), f("2")))
print("%-4s|%s" % (C("c"), f("3")))
print("%a and %s" % (C("é"), f("4")))
print("%5.2s|%+s|% s|%#r|%05s" % (C("d"), C("e"), C("f"), C("g"), C("h")))
print("%12s|%.12s|%s" % (C("i"), C("j"), f("5")))
print("100%% %s %s" % (C("k"), f("6")))
print("%-100s|%s" % (C("l"), f("7")))
print("%.100s|%s" % (C("m"), f("8")))
print("%s %d" % (C("n"), len(f("9"))))
t = (C("o"), f("10"))
print("%s %s" % t)
print(FMT % (C("p"), f("11")))
try:
    print("%s %s %s" % (C("q"), boom(), C("r")))
except KeyError as e:
    print("KeyError", e)
try:
    print("%s %s" % (Bad(), f("12")))
except ValueError as e:
    print("ValueError", e)
try:
    print("%s %s %d" % (Bad(), f("13"), 1))
except ValueError as e:
    print("ValueError", e)
try:
    print("%s" % (C("s"), f("14")))
except TypeError as e:
    print("TypeError", e)
try:
    print("%s %s %s" % (C("t"), f("15")))
except TypeError as e:
    print("TypeError", e)
