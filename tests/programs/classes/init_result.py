# Construction validates the result after __init__ runs, including inherited initializers.
class Bad:
    def __init__(self, n: int) -> int:
        print("init", n)
        return 0


class Inherited(Bad):
    pass


def arg() -> int:
    print("arg")
    return 7


try:
    Bad(arg())
    print("constructed")
except TypeError as e:
    print("TypeError", e)
try:
    Inherited(8)
    print("constructed inherited")
except TypeError as e:
    print("TypeError", e)


class Raises:
    def __init__(self) -> int:
        print("raising")
        raise ValueError("initializer")


try:
    Raises()
except ValueError as e:
    print("ValueError", e)


class Explicit(Bad):
    def __init__(self, n: int) -> None:
        # Calling a base's __init__ directly is legal even when it returns a value.
        print("super result", super().__init__(n))


Explicit(9)
