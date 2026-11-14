# error: star_list_default.py:10: error: unpacking a list[int] into the arguments of __main__.f() is not supported where its items may fill 'b', a parameter with a default or given by keyword
# A run-time list unpacks into *args after the parameters without defaults
# (star_list_varargs.py); one whose length decides whether b takes an item or its default is
# not supported.
def f(a: int, b: int = 2, *args: int) -> int:
    return a + b + sum(args)


xs = [1, 2, 3]
print(f(*xs))
