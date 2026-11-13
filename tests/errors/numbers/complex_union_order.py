# error: comparing closed union values requires narrowing with isinstance() first
def f(v: int | complex) -> bool:
    return v < 1


print(f(0))
