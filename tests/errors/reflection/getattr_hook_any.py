# error: getattr_hook_any.py:13: error: a Proxy object as an Any value is not supported: its class defines __getattr__, which the attribute lookups of an Any value do not call (#1536)
# An Any value's attribute is found among its class's at run time, where no case calls the
# class's __getattr__: an object of such a class cannot become an Any value.
# pystachy: dynamic-any
from typing import Any


class Proxy:
    def __getattr__(self, name: str) -> int:
        return 7


x: Any = Proxy()
print(x.port)
