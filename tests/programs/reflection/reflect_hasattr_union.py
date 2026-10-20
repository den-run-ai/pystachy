# hasattr(o, "name") with a literal name where o may be an object of one of several classes (a
# union of classes, also with None): each class's answer, a field's flag or a property's getter
class A:
    def __init__(self, f: bool) -> None:
        self.a = 1
        if f:
            self.opt = 2


class B:
    def __init__(self) -> None:
        self.b = "b"

    @property
    def p(self) -> int:
        raise AttributeError("no p")


def pick(i: int) -> A | B | None:
    if i == 0:
        return A(True)
    if i == 1:
        return A(False)
    if i == 2:
        return B()
    return None


for i in range(4):
    o = pick(i)
    print(hasattr(o, "a"), hasattr(o, "b"), hasattr(o, "opt"), hasattr(o, "p"), hasattr(o, "__class__"), hasattr(o, "__dict__"))
    if hasattr(o, "b"):
        print("has b")
