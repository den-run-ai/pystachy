# error: expected _ParameterKind, got int
# A parameter's kind is a member of the kinds' enum class: CPython also takes its int, as an
# IntEnum member is one there (docs: lib/compatibility.md#inspect)
import inspect

print(inspect.Parameter("x", 1).kind)
