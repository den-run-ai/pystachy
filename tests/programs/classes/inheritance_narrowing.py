# A runtime subclass test refines stable local reads without changing storage or identity.
class Base:
    def __init__(self, n: int) -> None:
        self.n = n


class Child(Base):
    def __init__(self, n: int, assigned: bool = True) -> None:
        super().__init__(n)
        self.items: list[str] = ["start"]
        if assigned:
            self.extra = n + 10

    def value(self) -> int:
        return self.extra


class Deep(Child):
    def value(self) -> int:
        return self.extra + 100


class Sibling(Base):
    pass


def branch(obj: Base) -> None:
    if isinstance(obj, Child):
        alias: Base = obj
        obj.extra += 1
        obj.items = []
        obj.items.append("changed")
        print("child", obj.extra, obj.value(), obj is alias, obj.items)
        if isinstance(obj, Deep):
            print("deep", obj.value())
    else:
        print("other", obj is None)


def guard(obj: Base | None) -> int:
    if not isinstance(obj, Child):
        return -1
    return obj.extra + obj.value()


def asserted(obj: Base) -> int:
    local = obj
    assert isinstance(local, Child)
    return local.extra


def boolean(obj: Base) -> None:
    if isinstance(obj, Child) and obj.extra > 0:
        print("and", obj.value())
    if not isinstance(obj, Child) or obj.extra > 0:
        print("or")
    else:
        print("else", obj.extra)


def loop(obj: Base, replacement: Base) -> None:
    while isinstance(obj, Child):
        print("loop", obj.extra)
        obj = replacement
    print("loop end", obj is replacement)


def snapshot(values: list[Base]) -> None:
    obj = values[0]
    if isinstance(obj, Child):
        values[0] = Base(90)
        print("snapshot", obj.extra, obj is values[0])


objects: list[Base | None] = [Base(0), Child(1), Deep(2), Sibling(3), None]
for obj in objects:
    branch(obj)
    print("guard", guard(obj))
    try:
        print("assert", asserted(obj))
    except AssertionError:
        print("assert failed")
    boolean(obj)
loop(Child(4), Base(5))
snapshot([Deep(6)])
try:
    branch(Child(7, False))
except AttributeError as error:
    print("AttributeError:", error)
