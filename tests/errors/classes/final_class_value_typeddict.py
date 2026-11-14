# error: final_attr_support/fattrs_typeddict.py:5: error: a field annotated Final without a type needs a constant value (int, float, str or bool): annotate it Final[T]
# An imported class that is not compiled keeps the rejection, though the program does not use
# it: CPython's import fails where TypedDict reads the annotation (TypeError: Plain typing.Final
# is not valid as type argument).
import final_attr_support.fattrs_typeddict

print("imported")
