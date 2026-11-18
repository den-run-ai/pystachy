# Documented deviation (lib/compatibility.md#inspect): replace() makes its copy by the class's
# name, where CPython calls type(self): a call of a class as a value would take the kind as an
# Any value, which an IntEnum member cannot be. For an object of a subclass it raises
# NotImplementedError rather than return a Parameter or a Signature, where CPython prints
# <Field "b"> and <Shape (a)>.
import inspect


class Field(inspect.Parameter):
    pass


class Shape(inspect.Signature):
    pass


f = Field("a", inspect.Parameter.POSITIONAL_OR_KEYWORD)
print(repr(f), repr(inspect.Parameter("a", inspect.Parameter.KEYWORD_ONLY).replace(name="b")))
try:
    print(repr(f.replace(name="b")))
except NotImplementedError as e:
    print("NotImplementedError:", e)
try:
    print(repr(Shape([f]).replace()))
except NotImplementedError as e:
    print("NotImplementedError:", e)
