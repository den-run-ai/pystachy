# error: issubclass() with a tuple inside its tuple of classes is not supported
class A:
    pass


def check(k: type) -> bool:
    return issubclass(k, ((int, str), A))


print(check(A))
