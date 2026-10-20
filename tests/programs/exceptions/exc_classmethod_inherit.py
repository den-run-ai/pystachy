# A class method that an exception class inherits: one that uses cls is compiled again for the
# subclass, whose name its cls then reads (cls(...) makes a subclass object, cls.x reads the
# subclass's class attribute, cls.m() calls its class method); one that does not use cls is
# shared, as a static method is. C.__name__ (also cls.__name__) is the class's name.
from typing import Self


class BaseErr(Exception):
    tag = "base"
    made: list[str] = []

    def __init__(self, msg: str, code: int | None = None) -> None:
        super().__init__(msg)
        self.code = code

    @classmethod
    def make(cls, code: int) -> "BaseErr":
        cls.made.append(cls.__name__)
        return cls("code " + str(code), code)

    @classmethod
    def named(cls) -> str:
        return cls.__name__ + "/" + cls.tag + "/" + cls.kind()

    @classmethod
    def kind(cls) -> str:
        return "k:" + cls.tag

    @classmethod
    def plain(cls, x: int) -> int:
        return x * 2

    @classmethod
    def same(cls, msg: str) -> Self:
        return cls(msg)

    @staticmethod
    def at(code: int | None) -> "BaseErr":
        return BaseErr("at " + str(code), code)


class SubErr(BaseErr):
    tag = "sub"


class Leaf(SubErr):
    def __init__(self, msg: str, code: int | None = None) -> None:
        super().__init__(msg, code)
        self.extra = [1, 2, 3]


e = SubErr.make(5)
print(type(e).__name__, isinstance(e, SubErr), isinstance(e, Leaf), e, repr(e), e.code)
for x in [BaseErr.make(7), SubErr.make(7), Leaf.make(7)]:
    try:
        raise x
    except Leaf as y:
        print("leaf", y, y.code, y.extra)
    except SubErr as y:
        print("sub", y, y.code)
    except BaseErr as y:
        print("base", y, y.code)
print(BaseErr.made, SubErr.made is BaseErr.made)
print(BaseErr.named(), SubErr.named(), Leaf.named())
print(BaseErr.plain(2), SubErr.plain(3), Leaf.plain(4))
s = Leaf.same("m")
print(type(s).__name__, s.extra, str(s))
try:
    raise SubErr.at(3)
except SubErr:
    print("not this")
except BaseErr as z:
    print("static", type(z).__name__, z, z.code)
lf = Leaf("q")
print(lf.named(), lf.kind(), BaseErr.__name__, Leaf.__name__)
