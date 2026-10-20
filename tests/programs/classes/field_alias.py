# The loads and stores of object fields carry TBAA tags (fieldtbaa, docs/typed-ir.md): what two
# references may reach as one field keeps its order, whichever class each reference names: a base
# and a derived class (an inherited field, an "is assigned" flag), two references of one class, and
# exception classes. The objects come out of a list, so that LLVM cannot tell they are one.
import sys


class Base:
    def __init__(self, a: int, w: float) -> None:
        self.a = a
        self.w = w


class Derived(Base):
    def __init__(self, a: int, w: float, b: int) -> None:
        super().__init__(a, w)
        self.b = b


class Lazy:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.v = -1


class LazyChild(Lazy):
    def __init__(self) -> None:
        super().__init__(False)
        self.u = 0


class AppError(ValueError):
    def __init__(self, code: int) -> None:
        super().__init__("app")
        self.code = code


class DetailError(AppError):
    def __init__(self, code: int, detail: str) -> None:
        super().__init__(code)
        self.detail = detail


def base_reads(base: Base, derived: Derived, n: int) -> int:
    s = 0
    for i in range(n):
        derived.a = i  # (an inherited field: the next read through base finds it)
        s += base.a
        derived.b = s
    return s


def derived_reads(base: Base, derived: Derived, n: int) -> float:
    t = 0.0
    for i in range(n):
        base.w = i * 0.5
        t += derived.w
    return t


def one_class(p: Base, q: Base, n: int) -> int:
    s = 0
    for i in range(n):
        p.a = i
        q.w = 1.5  # (another field: p.a stays)
        s += q.a + p.a
    return s


def flags(x: Lazy, y: LazyChild, n: int) -> int:
    s = 0
    for i in range(n):
        y.v = i  # (the field and its flag, through the derived class)
        s += x.v
        y.u = s
    return s


def codes(e: AppError, d: DetailError, n: int) -> int:
    s = 0
    for i in range(n):
        d.code = i
        s += e.code
    return s


n = 100 * len(sys.argv)
d = Derived(7, 0.25, 0)
ds: list[Derived] = [d, d, Derived(3, 2.0, 0)]
bs: list[Base] = [ds[0], ds[2]]
print(base_reads(bs[0], ds[1], n), d.a, d.b)
print(base_reads(bs[1], ds[1], n), ds[2].a, ds[2].b)
print(derived_reads(bs[0], ds[1], n), d.w)
print(derived_reads(bs[1], ds[1], n), ds[2].w)
print(one_class(bs[0], ds[1], n), d.a, d.w)
print(one_class(bs[1], ds[1], n), ds[2].a, ds[2].w)
lz = LazyChild()
print(hasattr(lz, "v"))
ls: list[LazyChild] = [lz, lz]
lzs: list[Lazy] = [ls[0], Lazy(True)]
print(flags(lzs[0], ls[1], n), lz.v, lz.u)
print(flags(lzs[1], ls[1], n), lzs[1].v)
de = DetailError(1, "x")
des: list[DetailError] = [de, de]
es: list[AppError] = [des[0], AppError(5)]
print(codes(es[0], des[1], n), de.code, de.detail)
print(codes(es[1], des[1], n), es[1].code)
try:
    raise des[0]
except AppError as e:
    print(e.code, str(e))
