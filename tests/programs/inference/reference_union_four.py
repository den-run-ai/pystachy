class A:
    def label(self) -> str:
        return "a"


class B:
    def label(self) -> str:
        return "b"


class C:
    def label(self) -> str:
        return "c"


class D:
    def label(self) -> str:
        return "d"


def widen(value: A | B) -> A | B | C | D:
    return value


items: list[A | B | C | D] = [widen(A()), widen(B()), C(), D()]
for item in items:
    print(item.label())
