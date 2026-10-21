# Exception construction checks __init__ too, including inherited and class-value calls.
class BadError(Exception):
    def __init__(self, n: int) -> int:
        print("error init", n)
        super().__init__(n)
        return 0


class ChildError(BadError):
    pass


def make(kind: type[Exception], n: int) -> None:
    try:
        raise kind(n)
    except TypeError as e:
        print("TypeError", e)
    except BadError:
        print("wrong exception")


try:
    raise BadError(1)
except TypeError as e:
    print("TypeError", e)
except BadError:
    print("wrong exception")
try:
    ChildError(2)
except TypeError as e:
    print("TypeError", e)
make(BadError, 3)
make(ChildError, 4)


class ExceptionResult:
    def __init__(self) -> Exception:
        return ValueError("result")


try:
    ExceptionResult()
except TypeError as e:
    print("TypeError", e)
