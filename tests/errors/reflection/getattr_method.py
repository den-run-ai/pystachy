# error: getattr_method.py:10: error: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find)
# CPython calls __getattr__ where reading an attribute fails, here a field that __init__ may
# leave unassigned, which Pystachy reports as an AttributeError.
class Config:
    def __init__(self, full: bool) -> None:
        if full:
            self.depth = 3
        self.name = "c"

    def __getattr__(self, name: str) -> int:
        return 0


print(Config(False).depth)
