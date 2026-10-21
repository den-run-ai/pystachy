# error: duplicate argument 'a' in function definition
def f(a: int, a: int = 2) -> int:
    return a


print(f(1))
