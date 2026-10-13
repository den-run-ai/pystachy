# error: union_len.py:4: error: unsupported call len(int | str): narrow it to one of its types first, with isinstance()
# len() of a value that may be an int
def f(x: int | str) -> int:
    return len(x)


print(f("ab"))
