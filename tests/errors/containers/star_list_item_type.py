# error: star_list_item_type.py:9: error: unpacking a list[int] into the arguments of __main__.f(), whose *args takes float items, is not supported (make it a list[float])
# The tuple that *args is holds the list's items as they are: a list of another item type than
# the annotation's would need each item converted.
def f(*args: float) -> float:
    return sum(args)


xs = [1, 2, 3]
print(f(*xs))
