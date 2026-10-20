# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, printf-style % of an Any str is not implemented: it raises TypeError where CPython
# formats (here it would print R() twice). It never runs the right operand's __rmod__, which
# CPython's str % does not call either. A str known as such formats an Any value.
# pystachy: dynamic-any
from typing import Any


class R:
    def __rmod__(self, other: str) -> str:
        return "R.__rmod__"

    def __str__(self) -> str:
        return "R()"


fmt: Any = "%s"
r: Any = R()
print("%s" % r)
print(fmt % r)
