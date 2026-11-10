# error: minmax_default_type.py:5: error: default= of max() must be None or of the items' type, float, not int
# A default of another type than the items would give the result two types: CPython's max()
# of an empty list here is the int 0, of any other a float
values: list[float] = []
print(max(values, default=0))
