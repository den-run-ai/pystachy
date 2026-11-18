# error: getattr_hook_signature.py:5: error: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find) unless it is an instance method def __getattr__(self, name)
# Pystachy calls a __getattr__ that takes the object and the name (#1536): one with another
# parameter, also with a default, stays an error.
class Proxy:
    def __getattr__(self, name: str, fallback: int = 0) -> int:
        return fallback


print(Proxy().depth)
