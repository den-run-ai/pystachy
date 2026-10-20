# Keyword names that match methodcaller's positional-only and variadic parameters
# are forwarded to the target; they never replace its literal method name.
from operator import attrgetter, itemgetter, methodcaller


class Target:
    def expected(self, name: str, args: str, kwargs: str) -> str:
        return "expected:" + name + args + kwargs

    def wrong(self, name: str, args: str, kwargs: str) -> str:
        return "wrong:" + name + args + kwargs


f = methodcaller("expected", name="wrong", args="a", kwargs="k")
print(f(Target()))
print(repr(f))

# C getters use object.__init__: direct and bound calls evaluate their arguments,
# but retain the original selection and positional/keyword arguments.
def argument(value: int) -> int:
    print("argument", value)
    return value


g = itemgetter(0)
g.__init__(argument(1))
reset = g.__init__
reset(argument(2))
print(g([10, 20, 30]), repr(g))
h = methodcaller("upper")
h.__init__("lower")
print(h("aBc"), repr(h))


class Fields:
    def __init__(self) -> None:
        self.x = 3
        self.y = 7


a = attrgetter("x")
a.__init__("y")
print(a(Fields()), repr(a))
