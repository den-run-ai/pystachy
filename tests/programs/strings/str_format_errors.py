# str.format() errors raise when the call runs, as CPython's do: a malformed format, mixed
# numbering, a missing argument or keyword, a bad conversion or attribute, a spec nested too
# deeply, a keyword given twice; once the arguments are evaluated, and after the fields before
# the error are formatted (their __format__ runs)


class Loud:
    def __init__(self, name: str) -> None:
        self.name = name

    def __format__(self, spec: str) -> str:
        print("  format", self.name, repr(spec))
        return self.name


def arg(v: str) -> str:
    print("  arg", v)
    return v


def report(e: Exception) -> None:
    print(" ", type(e).__name__, repr(str(e)))


print("malformed")
try:
    print("{".format())
except ValueError as e:
    report(e)
try:
    print("ab}".format())
except ValueError as e:
    report(e)
try:
    print("{0}}x".format(Loud("a")))
except ValueError as e:
    report(e)
try:
    print("{{}".format())
except ValueError as e:
    report(e)
try:
    print("{0".format(1))
except ValueError as e:
    report(e)
try:
    print("{0[}".format([1]))
except ValueError as e:
    report(e)
try:
    print("{0[0}".format([1]))
except ValueError as e:
    report(e)
try:
    print("{0!".format(1))
except ValueError as e:
    report(e)
try:
    print("{0!r".format(1))
except ValueError as e:
    report(e)
try:
    print("{!}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0!}x".format(1))
except ValueError as e:
    report(e)
try:
    print("{0!rr}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0:".format(1))
except ValueError as e:
    report(e)
try:
    print("{0:{".format(1))
except ValueError as e:
    report(e)
try:
    print("{a{}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0[0]x}".format([1]))
except ValueError as e:
    report(e)
try:
    print("{0.}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0..x}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0[]}".format([1]))
except ValueError as e:
    report(e)
try:
    print("{99999999999999999999}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0[99999999999999999999]}".format([1]))
except ValueError as e:
    report(e)
try:
    print("{99999999999999999999x}".format(1))
except ValueError as e:
    report(e)

print("numbering")
try:
    print("{}{0}".format(Loud("a"), 2))
except ValueError as e:
    report(e)
try:
    print("{0}{}".format(Loud("a"), 2))
except ValueError as e:
    report(e)
try:
    print("{0:{}}".format(1, 2))
except ValueError as e:
    report(e)
try:
    print("{:{0}}".format(1, 2))
except ValueError as e:
    report(e)
print("{a}{}{b}{}".format(1, 2, a="A", b="B"))
print("{a}{0}{b}{1}".format(1, 2, a="A", b="B"))

print("missing arguments")
try:
    print("{}{}{}".format(arg("x"), arg("y")))
except IndexError as e:
    report(e)
try:
    print("{0}{9}".format(Loud("a")))
except IndexError as e:
    report(e)
try:
    print("{}".format())
except IndexError as e:
    report(e)
try:
    print("{a}{b}".format(a=Loud("a")))
except KeyError as e:
    report(e)
try:
    print("{ 0}".format(1))
except KeyError as e:
    report(e)
try:
    print("{é}".format(1))
except KeyError as e:
    report(e)
try:
    print("{-1}".format(1))
except KeyError as e:
    report(e)
xs = ["p", "q"]
try:
    print("{}{}{}".format(*xs))
except IndexError as e:
    report(e)
try:
    print("{0}{1}{4}".format("z", *xs))
except IndexError as e:
    report(e)
d = {"a": 1}
try:
    print("{a}{b}".format(**d))
except KeyError as e:
    report(e)
try:
    print("{x}".format_map(d))
except KeyError as e:
    report(e)
try:
    print("{a}{}".format_map(d))
except ValueError as e:
    report(e)
try:
    print("{0}".format_map(d))
except ValueError as e:
    report(e)

print("lookups")
try:
    print("{0[5]}".format([1, 2]))
except IndexError as e:
    report(e)
try:
    print("{0[a]}".format(d))
except KeyError as e:
    report(e)
try:
    print("{0[9]}".format("abc"))
except IndexError as e:
    report(e)

print("conversions")
try:
    print("{0!x}".format(arg("v")))
except ValueError as e:
    report(e)
try:
    print("{0!q:>3}".format(1))
except ValueError as e:
    report(e)
try:
    print("{9!q}".format(1))
except IndexError as e:
    report(e)
try:
    print("{0!é}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0!€}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0!\n}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0!\x7f}".format(1))
except ValueError as e:
    report(e)
try:
    print("{0!r:{1!}}".format(1, 2))
except ValueError as e:
    report(e)

print("specs")
try:
    print("{:{:{}}}".format(1, 2, 3))
except ValueError as e:
    report(e)
try:
    print("{0:{1:{2}}}".format(1, 2, 3))
except ValueError as e:
    report(e)
try:
    print("{:{{}}}".format(1))
except ValueError as e:
    report(e)
try:
    print("{:d}".format("x"))
except ValueError as e:
    report(e)
try:
    print("{0:{1}}".format(Loud("a"), arg("spec")))
except ValueError as e:
    report(e)
n: str | None = None
try:
    print("{:>4}".format(n))
except TypeError as e:
    report(e)
try:
    print("{0}{1:,d}".format(Loud("a"), 1.5))
except ValueError as e:
    report(e)

print("keywords")
try:
    print("{a}".format(a=arg("1"), **{"a": arg("2")}, b=arg("3")))
except TypeError as e:
    report(e)
try:
    print("{a}".format(**d, a=arg("4")))
except TypeError as e:
    report(e)
try:
    print("{a}".format(a=arg("5"), **d))
except TypeError as e:
    report(e)
# (the keywords after a ** are evaluated before a name it gave is reported; of a dict merged
# after keywords, the first of its keys, in its order, that one of them has)
try:
    print("{a}".format(**d, a=arg("6"), c=arg("7")))
except TypeError as e:
    report(e)
try:
    print("{a}".format(**{"a": "x"}, a=arg("8"), c=arg("9")))
except TypeError as e:
    report(e)


def given(**kwargs: str) -> None:
    try:
        print("{a}".format(**kwargs, a=arg("10"), c=arg("11")))
    except TypeError as e:
        report(e)


given(a="x")
try:
    print("{a}{c}".format(arg("p1"), c=arg("k1"), *(arg("p2"),), **{"b": arg("d1")}, a=arg("k2"), e=arg("k3")))
except TypeError as e:
    report(e)
ba = {"b": "3", "a": "4"}
try:
    print("{a}{b}".format(a=1, b=2, **ba))
except TypeError as e:
    report(e)
try:
    print("{a}{b}".format(**{"x": 1, "a": 2, "z": 3}, **ba))
except TypeError as e:
    report(e)
none: tuple[int, int] | None = None
try:
    print("{}".format(*none))
except TypeError as e:
    report(e)
nd: dict[str, int] | None = None
try:
    print("{a}".format(**nd))
except TypeError as e:
    report(e)
