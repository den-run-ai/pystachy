# error: g() missing 1 required keyword-only argument: 'b'
def g(a: int, *, b: int) -> int:
    return a + b


print(g(1))
