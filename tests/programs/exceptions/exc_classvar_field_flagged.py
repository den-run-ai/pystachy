# A subclass's class variable shadows a field its exception base may leave unassigned: the base's
# read of the field finds the subclass's class attribute (CPython looks it up on the object's
# class), and raises AttributeError, naming the object's class, only for an object of a class
# without one. It once raised for the subclass's objects too.
class Base(Exception):
    def __init__(self, msg: str, flag: bool) -> None:
        super().__init__(msg)
        if flag:
            self.label = "base"

    def show(self) -> str:
        return self.label


class Sub(Base):
    label = "sub"

    def __init__(self) -> None:
        pass


class Plain(Base):
    pass


Sub.label = "changed"
print(Sub().show(), Base("x", True).show())
for b in [Base("y", False), Plain("z", False)]:
    try:
        print(b.show())
    except AttributeError as e:
        print("AttributeError", e)
