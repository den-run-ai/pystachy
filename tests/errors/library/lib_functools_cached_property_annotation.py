# error: lib_functools_cached_property_annotation.py:7: error: @cached_property method A.v() needs a return annotation: the type of the value it keeps
from functools import cached_property


class A:
    @cached_property
    def v(self):
        return 3


print(A().v)
