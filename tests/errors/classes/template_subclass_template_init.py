# error: template_subclass_template_init.py:13: error: a subclass of class template Base whose own __init__ is a class template is not supported: annotate the parameters of Child.__init__ with concrete types (not Any or object)
# A subclass of a class template derives from one specialization of it, which its __init__'s
# super().__init__(...) decides where the class is declared: an __init__ that is a template
# itself, whose objects would each pick their own, cannot decide it.
class Base:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Child(Base):
    def __init__(self, value):
        super().__init__(value)


print(Child(1).get())
