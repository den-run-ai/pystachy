# A class's name read in functions that bind no local of that name reads the class: through a
# comprehension variable of the same name, cls in a class method, Base.__init__(self, ...) of an
# exception class, raise, except and isinstance(), and in an expression typed ahead of where it
# runs (errors/class_local_*.py: where the function assigns the name, its reads before the
# assignment are errors)
class A:
    k: int = 7

    @staticmethod
    def f() -> int:
        return 1

    @classmethod
    def g(cls) -> int:
        return cls.k + cls.f()


class E(Exception):
    def __init__(self, m: str) -> None:
        Exception.__init__(self, m)


def comp() -> list[int]:
    xs = [A for A in range(3)]
    return xs + [A.k, A.f(), A.g()]


def uses() -> str:
    try:
        raise E("x")
    except E as e:
        return str(e) + str(isinstance(e, E)) + A.__name__


def filled_later(o: A) -> list[int]:
    # (typing xs where print(xs) reads it reads A.k from further on, where A is the local)
    xs = []
    print(xs)
    A = o
    xs.append(A.k)
    return xs


print(comp(), uses())
print(filled_later(A()))
