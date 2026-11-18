# error: closed union operations require narrowing with isinstance() first
def f(v: int | complex) -> bool:
    return [v] == [v]


print(f(1))
