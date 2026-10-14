# Truth and string conversion select the concrete subclass's added protocol, retaining the
# ordinary-object fallback for siblings without one and None's own behavior.
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class BoolOnly(Base):
    def __bool__(self) -> bool:
        return self.n == 0


class LenOnly(Base):
    def __len__(self) -> int:
        return self.n


class ReprOnly(Base):
    def __repr__(self) -> str:
        return "repr:" + str(self.n)


class StrOnly(Base):
    def __str__(self) -> str:
        return "str:" + str(self.n)


class PlainChild(Base):
    pass


class FormatOnly(Base):
    def __format__(self, spec: str) -> str:
        return "format:" + str(self.n) + ":" + spec


def truth(obj: Base) -> bool:
    return bool(obj)


print(truth(Base(0)), truth(BoolOnly(0)), truth(BoolOnly(1)))
print(truth(LenOnly(0)), truth(LenOnly(2)))
try:
    print(truth(LenOnly(-1)))
except ValueError as e:
    print("ValueError:", e)
rep: Base = ReprOnly(3)
st: Base = StrOnly(4)
plain: Base = PlainChild(5)
print(str(rep), repr(rep), str(st))
print(repr(st).startswith("<__main__.StrOnly object at 0x"))
print(str(plain).startswith("<__main__.PlainChild object at 0x"))
print(repr(plain).startswith("<__main__.PlainChild object at 0x"))
maybe: Base | None = None
print(bool(maybe), str(maybe), repr(maybe))
maybe = ReprOnly(6)
print(bool(maybe), str(maybe), repr(maybe))


def formatted(obj: Base, spec: str) -> None:
    print(format(obj), f"{obj}")
    try:
        print(format(obj, spec))
    except TypeError as e:
        print("TypeError:", e)


formatted(FormatOnly(7), "custom")
formatted(ReprOnly(8), "")
formatted(StrOnly(9), "custom")
formatted(None, "custom")
