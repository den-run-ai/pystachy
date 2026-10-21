# error: tuple_runtime_concat_types.py:5: error: unsupported operand types for +: tuple[int, ...] and tuple[str, ...] (a runtime-length tuple holds items of one type)
# CPython's result holds ints and strs, which no runtime-length tuple's items are
a: tuple[int, ...] = (1,)
b: tuple[str, ...] = ("x",)
print(a + b)
