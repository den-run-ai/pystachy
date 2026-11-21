# error: getattr_hook_del.py:14: error: del of an attribute is only supported for a property (which calls its deleter)
# A deleted field reaches __getattr__ in CPython (#1536): deleting a field is not supported, with
# or without the method.
class Proxy:
    def __init__(self) -> None:
        self.x = 1

    def __getattr__(self, name: str) -> int:
        return 0


p = Proxy()
print(p.x)
del p.x
print(p.x)
