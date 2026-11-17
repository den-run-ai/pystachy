# __all__ bound by a top-level try statement's body and by an except clause that cannot run
# (tests/programs/imports/star_all_try_handler.py)
a = 3
b = 4
try:
    __all__ = ["a"]
except ValueError:
    __all__ = ["a", "b"]
