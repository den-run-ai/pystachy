# error: hash() of complex | int is not supported
def f(v: int | complex) -> int:
    return hash(v)


print(f(2j))
