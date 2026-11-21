# A class nested in a class body under a private name: CPython mangles the name it binds there
# (Outer._Outer__Hidden, which the body and its methods read as __Hidden) but not its __name__
# (__Hidden) or __qualname__ (Outer.__Hidden), and names in its own body mangle with Hidden.
# Outside the class, Outer._Outer__Hidden names it, also as a base and an annotation.
class Outer:
    class __Hidden:
        x = 1

        def __init__(self) -> None:
            self.__v = 5

        def show(self) -> str:
            return f"{type(self).__qualname__} {self.__v} {self._Hidden__v}"

    class __Error(Exception):
        pass

    first: __Hidden = __Hidden()

    def get(self) -> int:
        return self.__Hidden.x + Outer.__Hidden.x

    def fail(self) -> None:
        raise self.__Error("hidden")


class Sub(Outer._Outer__Hidden):
    pass


o = Outer()
h: Outer._Outer__Hidden = Sub()
print(isinstance(h, Outer._Outer__Hidden), type(h).__qualname__, h.show())
print(o.get(), Outer._Outer__Hidden.x, Outer._Outer__Hidden.__name__, Outer._Outer__Hidden.__qualname__)
print(Outer._Outer__Hidden().show(), Outer.first.show(), hasattr(o, "_Outer__Hidden"), hasattr(o, "__Hidden"))
try:
    o.fail()
except Exception as e:
    print(type(e).__name__, type(e).__qualname__, repr(e), type(e))
