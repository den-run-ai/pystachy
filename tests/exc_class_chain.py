# Three generations of exception classes, each with a field its __init__ may leave unassigned:
# the flags of each come before the fields of the next, as the methods of each read them.
class A(Exception):
    def __init__(self, x: int):
        super().__init__(x)
        if x > 0:
            self.a = x

    def get_a(self) -> int:
        return self.a


class B(A):
    def __init__(self, x: int, y: int):
        super().__init__(x)
        if y > 0:
            self.b = y

    def get_b(self) -> int:
        return self.b


class C(B):
    c: str

    def __init__(self, x: int, y: int, z: str):
        super().__init__(x, y)
        if z != "":
            self.c = z

    def get_c(self) -> str:
        return self.c


def probe(o: C) -> None:
    for i in range(3):
        try:
            if i == 0:
                print(o.get_a())
            elif i == 1:
                print(o.get_b())
            else:
                print(o.get_c())
        except AttributeError as e:
            print("AttributeError:", e)
            continue
        finally:
            print("probed", i)


for args in [(1, 2, "z"), (0, 2, ""), (1, 0, "q"), (0, 0, "")]:
    o = C(args[0], args[1], args[2])
    probe(o)
    print(repr(o), o == o, o == C(1, 1, "a"), o is o)
bs: list[A] = [C(1, 1, "a"), B(2, 0), A(3)]
for b in bs:
    try:
        raise b
    except C as e:
        print("C", e.get_c())
    except B as e:
        print("B", e.get_a())
    except A as e:
        print("A", e.get_a())
h: list[A] = []
try:
    raise h[0] if len(h) > 0 else A(5)
except A as e:
    try:
        raise e from None
    except Exception as e2:
        print("again", repr(e2))
