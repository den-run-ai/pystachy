# error: slice_assign_mixed.py:3: error: assigning a tuple[int,str] to a list slice is not supported: its items have different types
xs: list[int | str] = [1]
xs[:] = (1, "a")
