# error: template_under_class_attr.py:20: error: type object 'T' has no attribute 'unit'
# A class template under an ordinary class (#962) derives from no class itself, only its
# specializations do: a class attribute that only the base binds is read through an object
# (t.unit) or the base (Base.unit), not through the template's name.
class Base:
    unit = "cm"

    def __init__(self) -> None:
        self.n = 0


class T(Base):
    def __init__(self, v):
        super().__init__()
        self.v = v


t = T(3)
print(t.unit, Base.unit)
print(T.unit)
