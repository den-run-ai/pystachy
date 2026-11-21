# error: getattr_hook_template.py:8: error: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find) in a generic class or a class template (whose __init__ has an unannotated parameter)
# A class whose __init__ has an unannotated parameter is a template, specialized for each call's
# argument types: Pystachy calls the __getattr__ of a class with one layout only (#1536).
class Box:
    def __init__(self, v):
        self.v = v

    def __getattr__(self, name: str) -> int:
        return 0


print(Box(1).w, Box("a").w)
