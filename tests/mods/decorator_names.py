from functools import wraps


def inspect(f):
    print("decorate", f.__name__, f.__qualname__)
    return f


@inspect
def greet() -> str:
    return "hello"


@inspect
def make():
    @inspect
    def nested() -> int:
        return 42
    return nested


def traced(f):
    @wraps(f)
    def wrapped(x):
        return f(x)
    return wrapped


@traced
@inspect
def add(x: int) -> int:
    return x + 1
