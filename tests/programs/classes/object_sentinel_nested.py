# A nested function's sentinel default reads the module's sentinel where no enclosing
# function binds the name
S = object()


def g(x: int = S) -> bool:
    return True if x is S else False


def outer() -> bool:
    def f(x: int = S) -> bool:
        return g(x)
    return f()


def outer_given(n: int) -> bool:
    def f(x: int = S) -> bool:
        return g(x)
    return f(n)


def outer_local() -> bool:
    def f(x: int = S) -> bool:
        return True if x is S else False
    return f()


print(outer(), outer_given(4), outer_local(), g(), g(4))
