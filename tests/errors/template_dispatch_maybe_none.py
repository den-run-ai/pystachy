# error: unsupported operand type(s) for +: 'C' and 'int' (compiling f(C) for the call at tests/errors/template_dispatch_maybe_none.py:13, where o may be None
class C:
    pass


def f(o):
    if isinstance(o, C):
        return 1
    return o + 1


c = C()
print(f(c), f(C()), f(4))
