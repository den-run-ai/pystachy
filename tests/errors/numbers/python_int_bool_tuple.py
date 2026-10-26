# error: python_int_bool_tuple.py:6: error: expected tuple[int,int], got tuple[bool,int]
# pystachy: python-int
# A bool where a tuple holds a promoting int is rejected, as in a module that does not opt in:
# CPython keeps the bool, which prints as True
def pair(c: bool) -> None:
    t: tuple[int, int] = (c, 1)
    print(t)


pair(True)
