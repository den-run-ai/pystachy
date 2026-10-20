# error: comparing closed union values requires narrowing with isinstance() first
def less(a: int | str, b: int | str) -> bool:
    return a < b

print(less(1, 2))
