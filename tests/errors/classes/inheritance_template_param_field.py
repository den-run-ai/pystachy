# error: inheritance_template_param_field.py:11: error: cannot infer the type of field 'pending'
# (a class that a hierarchy's __init__ takes as a parameter is compiled as an ordinary class,
# used or not: each field of its __init__ needs a type; alone, it would be a template, whose
# fields the call that makes an object types)
from collections import deque


class Errors:
    def __init__(self) -> None:
        self.order: deque[str] = deque()
        self.pending = []


class Visitor:
    def __init__(self, errors: Errors) -> None:
        self.errors = errors


class Checker(Visitor):
    pass


print("unreached")
