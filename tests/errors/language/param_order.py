# error: parameter without a default follows parameter with a default
def f(a: int = 1, b: int) -> int:
    return a + b


print(f(b=2))
