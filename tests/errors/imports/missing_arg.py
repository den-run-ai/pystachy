# error: f() missing 1 required positional argument: 'b'
def f(a: int, b: int) -> int:
    return a + b
print(f(1))
