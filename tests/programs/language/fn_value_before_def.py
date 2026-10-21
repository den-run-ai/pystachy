# A function read as a value before its def statement has run: the function it calls is not
# defined yet when the call runs (NameError), as in CPython
def g() -> int:
    return h(1)


k = g
print(k is not None, k is g, k == g, k != len)
print(k())


def h(x):
    return x
