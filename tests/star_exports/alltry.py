a = 1
b = 2
try:
    __all__ = ["a"]
except ValueError:
    pass
