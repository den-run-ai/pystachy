# error: union_arith.py:4: error: + of a value of int | str is not supported: narrow it to one of its types first, with isinstance()
# arithmetic on a union of more than numbers
def f(x: int | str) -> int:
    return x + 1


print(f(1))
