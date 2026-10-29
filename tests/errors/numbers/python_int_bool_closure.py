# error: python_int_bool_closure.py:11: error: expected int, got bool
# pystachy: python-int
# A closure's builtin name may be one a function around it binds (here abs): a bool given to the
# closure's int parameter that it passes to one is rejected (CPython's abs here returns the bool)
def outer() -> None:
    abs = lambda v: v

    def inner(n: int) -> None:
        print(abs(n))

    inner(True)


outer()
