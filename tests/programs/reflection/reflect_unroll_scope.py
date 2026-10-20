# Unrolled loops over constant names: a parameter is no variable bound once (a loop may iterate
# its argument before the function binds it again); in a loop over dir(x) or vars(x), a variable
# x is narrowed to each exact class its copies are compiled for; an annotation without a value
# (self.y: int) assigns nothing, so the __dict__'s order is that of the assignments
class P:
    def __init__(self) -> None:
        self.x = 1
        self.y = 2
        self.z = 3


def f(p: P, names: list[str]) -> None:
    for n in names:
        print(n, hasattr(p, n))
    names = ["x", "y"]
    print("done")


f(P(), ["z", "q"])


class T:
    def test_b(self) -> None:
        print("b")

    def test_a(self) -> None:
        print("a")

    def helper(self) -> int:
        return 1


class U(T):
    def test_c(self) -> None:
        print("c")

    def test_a(self) -> None:
        print("a overridden")


def run(t: T) -> None:
    for name in dir(t):
        if name.startswith("test_"):
            getattr(t, name)()
        elif name.endswith("per"):
            print("helper", getattr(t, name)())
    else:
        print("done")


run(T())
run(U())


class V:
    def __init__(self) -> None:
        self.v = 1


class W(V):
    def __init__(self) -> None:
        super().__init__()
        self.w = 2.5


def show(o: V) -> None:
    for k in vars(o):
        print(k, getattr(o, k))


show(V())
show(W())


class Q:
    def __init__(self) -> None:
        self.b: int
        self.a = 1
        self.b = 2


print(vars(Q()))
