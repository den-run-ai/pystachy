# __all__ bound by a top-level try statement's body (tests/programs/imports/star_all_try.py)
a = 1
b = 2
try:
    __all__ = ["a"]
except ValueError:
    pass
