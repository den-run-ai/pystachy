# error: inheritance_template_field_unannotated.py:10: error: cannot infer the type of field 'deps'; annotate it (self.deps: T = ...)
# (a field that only the object __init__ stores types: the class is a template, whose
# specializations a subclass without an __init__ of its own extends (#962); the field's type is
# not known where the object is made, as without the subclass; annotating it gives it one)
from collections import defaultdict


class Base:
    def __init__(self) -> None:
        self.deps = defaultdict(set)


class Sub(Base):
    pass


print(len(Sub().deps))
