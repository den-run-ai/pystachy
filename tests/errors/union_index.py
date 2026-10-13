# error: union_index.py:4: error: 'list[int] | str' object is not subscriptable: narrow it to one of its types first, with isinstance()
# indexing a union: each member indexes differently (an int item, a str of one character)
def f(x: list[int] | str) -> int:
    return x[0]


print(f([1]))
