# pystachy: dynamic-any
# inspect from a module that opts in to dynamic Any, where mypyc's "default: object" is an Any
# variable that holds the marker and then a value of any type: the marker and a sentinel object
# keep their identity through it, and a class of the program is an annotation
import inspect
import sys
from typing import Any

_NOT_REPRESENTABLE = object()


class Point:
    pass


def find_default(i: int) -> Any:
    if i == 0:
        return None
    if i == 1:
        return 7
    if i == 2:
        return 2.5
    if i == 3:
        return (1, "a", None)
    if i == 4:
        return "text"
    if i == 5:
        return True
    return _NOT_REPRESENTABLE


def text_signature(n: int) -> str | None:
    parameters = []
    for i in range(n):
        default: Any = inspect.Parameter.empty
        if i > 0:
            default = find_default(i - 1)
            if default is _NOT_REPRESENTABLE:
                # This default argument cannot be represented in a __text_signature__
                return None
        curr_param = inspect.Parameter("p" + str(i), inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default)
        parameters.append(curr_param)
    return f"fn{inspect.Signature(parameters)}"


k = len(sys.argv) - 3  # 0, which only the run knows
for n in range(9):
    print(text_signature(n + k))

p = inspect.Parameter("pt", inspect.Parameter.KEYWORD_ONLY, annotation=Point, default=None)
print(p, inspect.Signature([p], return_annotation=Point), inspect.formatannotation(Point, "__main__"),
      inspect.formatannotation(Point), inspect.formatannotation(inspect.Parameter), p.annotation is Point)
items: list[Any] = [inspect.Parameter.empty, 1, inspect.Signature.empty, p, p.kind.value]
print(items[0] is items[2], items[0] is inspect._empty, items[1] is inspect._empty, items[:3], items[3], items[4])
value: Any = p
print(value.name, value.default is None, value.annotation is Point, str(value), value == p,
      isinstance(value, inspect.Parameter), value.replace(name="q", default=inspect.Parameter.empty))


def kind_name(x: Any) -> str:
    # (a kind is read from a parameter, which isinstance() makes of an Any value)
    if isinstance(x, inspect.Parameter):
        return x.kind.name + " " + str(x.kind == inspect.Parameter.KEYWORD_ONLY)
    return "no parameter"


typed: inspect.Parameter = items[3]
print(kind_name(value), kind_name(items[3]), kind_name(items[1]), typed.kind, typed.kind.description, typed is p)
sig: Any = inspect.Signature([p])
print(sig, len(sig.parameters), sig.return_annotation is inspect.Signature.empty, sig == inspect.Signature([value]),
      hash(sig) == hash(inspect.Signature([p])))
name: Any = "late"
kinds: dict[str, Any] = {"default": 5, "annotation": "int"}
q = inspect.Parameter(name, inspect.Parameter.POSITIONAL_ONLY, default=kinds["default"], annotation=kinds["annotation"])
print(q, q.default + 1, q.annotation.upper())
bad: Any = 3
try:
    inspect.Parameter(bad, inspect.Parameter.POSITIONAL_ONLY)
except TypeError as e:
    print("TypeError:", e)
