# Inherited fields keep their storage and assignment bits. A base constructor may call an
# override before a derived field is set, and base-typed references must see subsequent writes.
class Parent:
    def __init__(self, n: int, assigned: bool = True) -> None:
        self.n = n
        if assigned:
            self.optional = n + 1

    def read(self) -> int:
        return self.optional

    def set(self, n: int) -> None:
        self.optional = n


class Child(Parent):
    def __init__(self, n: int, assigned: bool = True) -> None:
        super().__init__(n, assigned)
        self.extra = n + 10


class Inherited(Child):
    pass


def show(obj: Parent) -> None:
    print(obj.n, hasattr(obj, "optional"))
    try:
        print(obj.read())
    except AttributeError as e:
        print("AttributeError:", e)
    obj.set(99)
    print(obj.optional, obj.read(), hasattr(obj, "optional"))


a = Child(1)
b = Inherited(2, False)
show(a)
show(b)
print(a.extra, b.extra, a.optional, b.optional)


class Early:
    def __init__(self) -> None:
        self.started = 1
        try:
            print(self.check())
        except AttributeError as e:
            print("AttributeError:", e)

    def check(self) -> int:
        return self.started


class Late(Early):
    def __init__(self) -> None:
        super().__init__()
        self.ready = 7

    def check(self) -> int:
        return self.started + self.ready


print(Early().check(), Late().check())
