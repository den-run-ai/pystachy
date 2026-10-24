# pystachy: dynamic-any
from typing import Any


class Base:
    fixed: float = float("nan")
    changing: int = int("1000")

    def __init__(self) -> None:
        self.own: float = float("nan")


class Child(Base):
    changing: int = int("1000")

    def __init__(self) -> None:
        super().__init__()
        self.extra: int = int("2000")


class Grandchild(Child):
    def __init__(self) -> None:
        super().__init__()
        self.last: int = int("3000")


class Plain:
    changing: float = float("nan")


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def base_read(o: Base) -> None:
    same("base view fixed", o.fixed, Base.fixed)
    same("base view own", o.own, o.own)
    same("base view changed", o.changing, Child.changing)


def run() -> None:
    a = Base()
    b = Grandchild()
    same("class default", a.fixed, Base.fixed)
    same("inherited default", b.fixed, Base.fixed)
    same("two objects", a.fixed, b.fixed)
    same("grandchild own", b.last, b.last)
    same("child own", b.extra, b.extra)
    same("distinct defaults", a.changing, b.changing)
    Child.changing = int("1000")
    base_read(b)
    same("updated class", b.changing, Child.changing)
    b.changing = int("1000")
    same("instance override", b.changing, Child.changing)
    Base.changing = int("1000")
    same("base class update", a.changing, Base.changing)
    p = Plain()
    same("plain default", p.changing, Plain.changing)
    Plain.changing = float("nan")
    same("plain update", p.changing, Plain.changing)
    p.changing = float("nan")
    same("plain override", p.changing, Plain.changing)


run()
