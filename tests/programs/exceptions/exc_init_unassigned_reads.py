# Reads in an exception class's __init__ that may run before what they read is assigned (#571):
# a module global that `raise E` reaches before the module assigns it, and a field read through
# a method called on self or super() before the field is assigned. Each raises as in CPython.


class E(Exception):
    def __init__(self) -> None:
        print(len(G))


def glen() -> int:
    return len(H)


class F(Exception):
    def __init__(self) -> None:
        super().__init__("F")
        print(glen())


try:
    raise E
except NameError as e:
    print("NameError:", e)
try:
    raise ValueError("v") from F
except NameError as e:
    print("NameError:", e)
G = "abc"
H = "de"
try:
    raise E
except E:
    print("E raised")
try:
    raise F
except F as f:
    print("F raised", f)


class B(Exception):
    def m(self) -> int:
        return len(str(self)) + 1


class C(B):
    def __init__(self) -> None:
        try:
            print(super().m())
        except AttributeError as e:
            print("AttributeError:", e)
        super().__init__("c")
        self.s = "xyz"
        print(super().m(), self.m())

    def __str__(self) -> str:
        return self.s


c = C()
print(c, c.s, c.m())


class C2(B):
    def __init__(self) -> None:
        try:
            print(self.m())
        except AttributeError as e:
            print("AttributeError:", e)
        super().__init__("c2")
        self.t = "uv"

    def __str__(self) -> str:
        return self.t


print(C2().m())


class D(B):
    def __init__(self, k: int) -> None:
        self.k = k
        super().__init__(k)
        print(super().m(), self.m())

    def __str__(self) -> str:
        return "d" * self.k


try:
    raise D(4)
except B as e:
    print("caught", e, e.m())
