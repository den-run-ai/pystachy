# error: a _ParameterKind member cannot become an Any value: an IntEnum member is an object of its class, where CPython's is also an int
# A kind is no default or annotation: an IntEnum member is no Any value (lib/compatibility.md#enum)
import inspect

print(inspect.Parameter("kind", inspect.Parameter.KEYWORD_ONLY, default=inspect.Parameter.KEYWORD_ONLY))
