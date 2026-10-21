# error: none_list_unfilled.py:4: error: cannot infer the type of 'xs', a list of None so far: annotate it (xs: list[T | None] = ...)
# A list of None that nothing fills: what it holds is unknown where it is read.
xs = [None] * 3
print(xs)
