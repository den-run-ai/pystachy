# a global that a function's store creates (global items) from x narrowed to the union of a
# class tuple keeps its declared type: the narrowing declines, and show() takes it as a Base
class Base:
    def name(self) -> str:
        return "base"


class A(Base):
    def name(self) -> str:
        return "A1"


class B(Base):
    def name(self) -> str:
        return "B1"


def show(b: Base) -> None:
    print(b.name())


def add(x: Base) -> None:
    global items, first, only
    if isinstance(x, (A, B)):
        items = [x]
        first = x
        only = x
        print(first.name(), len(items))


add(B())
show(items[0])
show(first)
show(only)
