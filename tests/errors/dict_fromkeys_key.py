# error: dict keys must be int or str, or tuples of int, bool, str and str | None items, not float
d = dict.fromkeys([0.5, 1.5], 0)
