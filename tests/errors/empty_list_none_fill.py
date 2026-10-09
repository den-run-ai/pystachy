# error: empty_list_none_fill.py:6: error: cannot infer the type of 'xs', an empty list so far
# An empty list read before the append that would type it, which appends None (a list[None]
# cannot be printed): the error names the read, not the line the look-ahead compiled.
def f() -> None:
    xs = []
    print(xs)
    xs.append(None)


f()
