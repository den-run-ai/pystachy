def py_set_error(kind: str, msg: str) -> None: ...


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


def boom(n: int) -> int:
    if n > 0:
        raise ValueError("boom " + str(n))
    return n


# what a compiler-generated entry wrapper would be: no Pystachy exception may unwind into CPython
def x_fib(n: int) -> int:
    try:
        return fib(n)
    except OverflowError as e:
        py_set_error("OverflowError", str(e))
        return 0


def x_boom(n: int) -> int:
    try:
        return boom(n)
    except ValueError as e:
        py_set_error("ValueError", str(e))
        return 0


def x_greet(n: int) -> str:
    return greet(n)


try:
    pass
except ValueError:
    pass


def x_hello(n: int) -> int:
    print("hello from pystachy", n)
    return n
