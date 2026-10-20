# error: none_list_extend_ints.py:5: error: cannot infer the type of 'xs', a list of None so far, from the int items of another list, which would need boxes: annotate it (xs: list[int | None] = ...)
# A list of None extended with ints: int | None items are boxes, and extend() copies.
def f() -> None:
    xs = [None] * 2
    xs.extend([1, 2])
    print(xs)


f()
