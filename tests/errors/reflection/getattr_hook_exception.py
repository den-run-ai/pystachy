# error: getattr_hook_exception.py:5: error: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find) in an exception class
# Pystachy calls the __getattr__ of an ordinary class (#1536); an exception class's stays an
# error, as an exception's attributes are its class's fields only.
class LazyError(Exception):
    def __getattr__(self, name: str) -> int:
        return 0


try:
    raise LazyError("lazy")
except LazyError as e:
    print(e.depth)
