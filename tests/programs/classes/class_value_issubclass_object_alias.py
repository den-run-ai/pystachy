# issubclass(k, base) of a class object k where base is object read through a variable: every
# class derives from object, as issubclass(k, object) answers where the name is written.
class A:
    pass


class B(A):
    pass


def check(k: type[A]) -> None:
    base = object
    print(issubclass(k, object), issubclass(k, base), issubclass(k, int))


check(A)
check(B)
missing: type[A] | None = None
if len([A]) > 1:
    missing = A
try:
    base = object
    print(issubclass(missing, base))
except TypeError as e:
    print("TypeError:", e)
