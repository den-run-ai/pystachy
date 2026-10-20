# error: closed union operations require narrowing with isinstance() first
def less(a: list[int | str], b: list[int | str]) -> bool:
    return a < b

print(less([1], [2]))
