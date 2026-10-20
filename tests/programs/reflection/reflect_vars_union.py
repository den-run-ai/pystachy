# vars() of a union of classes prints the member object's fields, not its union box (#569).
class A:
    def __init__(self) -> None:
        self.a = 1


class B:
    def __init__(self) -> None:
        self.c = "x"
        self.d = [1, 2]


class C:
    def __init__(self, n: float) -> None:
        self.n = n


o: A | B = B()
print(vars(o))
items: list[A | B | C] = [A(), B(), C(2.5)]
for it in items:
    print(vars(it), str(vars(it)) == repr(it.__dict__))
