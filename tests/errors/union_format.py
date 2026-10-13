# error: union_format.py:4: error: a format spec for a value of int | str is not supported: narrow it to one of its types first, with isinstance()
# a format spec, which each member reads its own way
def f(x: int | str) -> str:
    return f"{x:>5}"


print(f(1))
