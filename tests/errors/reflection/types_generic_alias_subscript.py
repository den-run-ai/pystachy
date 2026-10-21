# error: types_generic_alias_subscript.py:13: error: subscripting class 'Queue' at run time is not supported: CPython makes Queue[...] a types.GenericAlias (its __class_getitem__ = classmethod(GenericAlias)), and Pystachy has no generic aliases
# The idiom for a generic class defines nothing in Pystachy, so the class's subscripts at run time,
# CPython's types.GenericAlias objects, are an error (in annotations, and as a module's type alias,
# they name the class: tests/programs/reflection/types_generic_alias_subscripts.py)
from types import GenericAlias


class Queue:
    __class_getitem__ = classmethod(GenericAlias)


q = Queue()
print(Queue[int])
