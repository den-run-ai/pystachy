# error: inheritance_template_param_unannotated.py:11: error: cannot infer the type of field 'recorded'; annotate it (self.recorded: T = ...)
# (the class that the hierarchy's __init__ takes stores a class-template object into a field
# that nothing annotates: only the object types it, so the class is a template, and so is the
# hierarchy's, whose subclass without an __init__ of its own is supported (#962); the field's
# type is not known where the object is made, as without the hierarchy)
from collections import defaultdict


class Errors:
    def __init__(self) -> None:
        self.recorded = defaultdict(list)
        self.recorded["k"].append("v")


class Visitor:
    def __init__(self, errors: Errors) -> None:
        self.errors = errors


class Checker(Visitor):
    pass


print(len(Checker(Errors()).errors.recorded))
