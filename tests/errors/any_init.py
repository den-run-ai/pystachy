# error: any_init.py:8: error: typing.Any is only supported in the parameter and return annotations of a function, or of a method that may be a template (not __init__
# __init__ is no template (its parameters type the fields it assigns): a parameter it takes cannot
# be annotated Any, as one annotated object cannot (see object_param_init.py)
from typing import Any


class Holder:
    def __init__(self, value: Any) -> None:
        self.value = value


print(Holder(1).value)
