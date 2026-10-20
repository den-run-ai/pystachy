# A closure's nonlocal assignment undoes the narrowing an assignment gave the local (#570).
class Base:
    def name(self) -> str:
        return "base"


class Sub(Base):
    def name(self) -> str:
        return "sub"


def opt() -> None:
    x: str | None = "abc"

    def setn() -> None:
        nonlocal x
        x = None

    setn()
    try:
        print(len(x))
    except TypeError as e:
        print("TypeError:", e)
    print(x is None)


def hier() -> None:
    y: Base = Sub()

    def reset() -> None:
        nonlocal y
        y = Base()

    print(y.name())
    reset()
    print(y.name())


def union() -> None:
    z: int | str = 1

    def tostr() -> None:
        nonlocal z
        z = "one"

    tostr()
    print(z)


opt()
hier()
union()
