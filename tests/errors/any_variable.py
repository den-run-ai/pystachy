# error: any_variable.py:6: error: typing.Any is only supported in the parameter and return annotations of a function, or of a method that may be a template
# A variable annotated Any would hold a value of any type, which needs a box Pystachy does not
# have (#487): only a parameter or a return, which each call types, may be annotated Any
from typing import Any

x: Any = 5
print(x)
