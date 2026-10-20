# pystachy: dynamic-any
# An __init__ that takes *args: Any and **kwargs: Any, in a module that compiles typing.Any as
# dynamic values, makes objects as it does in modules that do not opt in (#782).
from typing import Any


class Variadic:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


v = Variadic(1, "two", label="three")
print(len(v.args), v.args[1], v.kwargs["label"])
w = Variadic()
print(len(w.args), len(w.kwargs))
