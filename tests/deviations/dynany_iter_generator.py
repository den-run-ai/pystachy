# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, an object whose __iter__ is a generator function does not iterate through an Any value
# yet, as a generator cannot become an Any value: TypeError, which names that, where CPython
# iterates it (here it would print 1 and 2).
# pystachy: dynamic-any
from typing import Any


class Gen:
    def __iter__(self):
        yield 1
        yield 2


g: Any = Gen()
try:
    for v in g:
        print(v)
except TypeError as e:
    print("TypeError:", e)
