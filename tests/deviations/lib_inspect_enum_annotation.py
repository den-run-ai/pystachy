# Documented deviation (lib/compatibility.md#inspect): an enum class as a value is an object of
# enum's EnumType here, which does not know its module, so that formatannotation() cannot write
# it as CPython writes a class: __main__.Color. It raises NotImplementedError rather than write
# the object's repr(), <enum 'Color'>. A parameter keeps the annotation, and its str() raises.
import enum
import inspect


class Color(enum.Enum):
    RED = 1


p = inspect.Parameter("c", inspect.Parameter.KEYWORD_ONLY, annotation=Color, default=Color.RED)
print(p.name, p.default, p.annotation is Color)
try:
    print(inspect.formatannotation(Color))
except NotImplementedError as e:
    print("NotImplementedError:", e)
print(p)
