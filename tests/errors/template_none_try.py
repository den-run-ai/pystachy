# error: template_none_try.py:4: error: unsupported operand type(s) for +: 'NoneType' and 'int' (compiling inc(None) for the call at tests/errors/template_none_try.py:9)
def inc(x):
    try:
        return x + 1  # (compiled for the call's types: x is None, whose TypeError the clause would catch)
    except TypeError:
        return 0


print(inc(None))  # (CPython: 0)
