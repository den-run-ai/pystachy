# error: inheritance_template_param_unannotated.py:14: error: inheritance with generic class templates is not supported: annotate __init__ parameters with concrete types (not Any or object)
# (the class that the hierarchy's __init__ takes stores a class-template object into a field
# that nothing annotates: only the object types it, so the class is a template, and so is the
# hierarchy's)
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
