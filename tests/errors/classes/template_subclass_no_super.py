# error: template_subclass_no_super.py:9: error: the __init__ of Child, a subclass of class template Base, must call super().__init__(...) once, in a statement of its own: the types of its arguments decide which specialization of Base its objects begin as
# An __init__ that does not call the template's own leaves the specialization that its objects
# begin as undecided (and one that calls it in a branch, or twice, may decide two).
class Base:
    def __init__(self, value):
        self.value = value


class Child(Base):
    def __init__(self, flag: bool) -> None:
        if flag:
            super().__init__(1)
        else:
            super().__init__("one")


print(Child(True).value)
