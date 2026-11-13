# issubclass(k, (a, b)) of a class object tests the tuple's items in order and stops at the
# first that k derives from: a later item that is None raises only where it is reached. Every
# item is evaluated before the test, and object read through a variable is every class's base.
class A:
    pass


class B(A):
    pass


def named(label: str, k: type) -> type:
    print("read", label)
    return k


def check(k: type, other: type | None) -> None:
    try:
        print(issubclass(k, (A, other)))
    except TypeError as e:
        print("TypeError:", e)


def ordered(k: type) -> None:
    print(issubclass(k, (named("first", A), named("second", int))))


def bases(k: type) -> None:
    base = object
    print(issubclass(k, object), issubclass(k, base), issubclass(k, (int, base)), issubclass(k, (str, A)))


check(A, None)
check(B, None)
check(A, int)
check(int, None)
check(int, int)
check(bool, int)
ordered(A)
ordered(bool)
ordered(str)
for k in [int, str, A, B, type(None)]:
    kind: type = k
    bases(kind)
