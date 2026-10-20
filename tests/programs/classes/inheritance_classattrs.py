# Inherited class attributes share their defining storage, while subclass declarations and
# instance writes shadow it. Reads through a base type use the receiver's concrete class.
class Parent:
    name: str = "parent"
    count: int = 1
    history: list[str] = []

    def __init__(self, own: bool = False) -> None:
        if own:
            self.count = 20

    def record(self, suffix: str = "!") -> str:
        self.history.append(self.name + suffix)
        return self.name + str(self.count)


class Child(Parent):
    name = "child"


class Grandchild(Child):
    count = 3


def report(obj: Parent) -> None:
    print(obj.name, obj.count, obj.record())


p = Parent()
c = Child()
g = Grandchild()
own: Parent = Child(True)
report(p)
report(c)
report(g)
report(own)
Parent.count = 5
print(p.count, c.count, g.count, own.count)
print(Parent.count, Child.count, Grandchild.count)
c.name = "instance"
report(c)
report(Child())
print(Parent.history, Parent.history is Child.history, Child.history is Grandchild.history)
