# A subclass's class variable shadows a field its exception base assigns in __init__: an object
# of the subclass that has not assigned the field reads the class's value, also through the
# base's code (a method, a parameter of the base's type, an except clause, hasattr), and a later
# assignment of the class variable shows there. The base's reads once found the field unassigned:
# 0 for an int, a null string.
class Base(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.label = "base"
        self.count = 1

    def show(self) -> str:
        return self.label.upper() + " " + str(self.count + 1)


class Sub(Base):
    label = "sub"
    count = 10

    def __init__(self) -> None:
        pass


class Deep(Sub):
    pass


def view(b: Base) -> str:
    return b.label + " " + str(hasattr(b, "label")) + " " + str(b.count)


print(Sub().show(), view(Sub()), view(Base("m")))
Sub.label = "changed"
Sub.count = 20
print(Sub().show(), Deep().show(), view(Deep()), view(Base("n")))
try:
    raise Deep()
except Base as e:
    print(e.label, e.count, e.show())
d = Deep()
d.label = "own"
print(view(d), d.show())
