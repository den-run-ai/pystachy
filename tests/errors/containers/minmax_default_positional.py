# error: minmax_default_positional.py:3: error: Cannot specify a default for max() with multiple positional arguments
# CPython's TypeError for default= with more than the one iterable
print(max(1, 2, default=0))
