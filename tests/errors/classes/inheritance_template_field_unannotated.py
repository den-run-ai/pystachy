# error: inheritance with generic class templates is not supported
# (a field that only the object __init__ stores types: the class is a template, whose
# specializations a subclass cannot extend; annotating the field gives it a type of its own)
from collections import defaultdict


class Base:
    def __init__(self) -> None:
        self.deps = defaultdict(set)


class Sub(Base):
    pass


print(len(Sub().deps))
