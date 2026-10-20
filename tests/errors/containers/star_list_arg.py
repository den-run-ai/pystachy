# error: star_list_arg.py:7: error: unpacking a list[int] into the arguments of __main__.three() is not supported (a tuple's items are)
def three(a: int, b: int, c: int) -> int:
    return a + b + c


xs = [1, 2, 3]
print(three(*xs))
