# The first program of a table of functions (tests/errors' fn_value_two before functions of one
# signature shared a Callable): a list of two defs, called through it.
def double(x: int) -> int:
    return x * 2


def triple(x: int) -> int:
    return x * 3


fs = [double, triple]
print([f(7) for f in fs], fs[0](1) + fs[1](1), len(fs))
