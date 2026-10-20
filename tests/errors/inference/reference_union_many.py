# error: reference unions support at most four members
class A:
    pass


class B:
    pass


class C:
    pass


class D:
    pass


class E:
    pass


def check(value: A | B | C | D | E) -> None:
    pass


check(A())
