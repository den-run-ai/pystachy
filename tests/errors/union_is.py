# error: union_is.py:4: error: 'is' between a value of int | str and one of int | str is not supported, only with None: compare them with ==
# identity of two union values (their boxes are not the values' identity)
def f(x: int | str, y: int | str) -> bool:
    return x is y


print(f(1, 2))
