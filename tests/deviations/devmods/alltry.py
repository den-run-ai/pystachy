# __all__ bound in a top-level try statement (tests/deviations/star_all_try.py)
a = 1
b = 2
try:
    __all__ = ["a"]
except ValueError:
    pass
