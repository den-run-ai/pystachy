# issubclass() evaluates its second argument before it checks its first: a class object that is
# None raises CPython's TypeError once both are evaluated.
class A:
    pass


class B(A):
    pass


def base() -> type[A]:
    print("base evaluated")
    return A


def check(k: type[A] | None) -> None:
    try:
        print(issubclass(k, base()))
    except TypeError as e:
        print("TypeError:", e)


check(B)
check(None)
