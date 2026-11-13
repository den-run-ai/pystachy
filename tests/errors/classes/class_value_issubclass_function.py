# error: issubclass() arg 2 must be a class, a tuple of classes, or a union
# A builtin function is no class: CPython raises this TypeError.
class C:
    pass


def check(k: type[C]) -> bool:
    return issubclass(k, len)


print(check(C))
