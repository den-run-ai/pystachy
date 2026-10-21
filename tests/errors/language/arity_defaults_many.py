# error: k() takes from 1 to 2 positional arguments but 3 were given
def k(a: int, b: int = 1) -> int:
    return a + b


print(k(1, 2, 3))
