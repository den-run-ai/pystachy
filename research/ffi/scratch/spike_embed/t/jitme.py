class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return "P(" + str(self.x) + ")"


def fib(n: int) -> int:
    a = 0
    b = 1
    for i in range(n):
        a, b = b, a + b
    return a


def greet(n: int) -> str:
    s = ""
    for i in range(n):
        s = s + str(i) + ","
    return s


def checked(n: int) -> int:
    try:
        return fib(n)
    except OverflowError:
        return -1


def boom(n: int) -> int:
    if n > 0:
        raise ValueError("boom " + str(n))
    return 0


def main() -> None:
    print("fib(50) =", fib(50), "checked(100) =", checked(100))
    print("len(greet(1000)) =", len(greet(1000)))
    print([P(1), P(2)])


main()
