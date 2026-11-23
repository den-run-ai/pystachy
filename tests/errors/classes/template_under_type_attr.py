# error: class 'T' cannot be used as a value: it is a class template (its __init__ has a parameter without an annotation)
# type(self) in a method of an ordinary class is the object's class, which for an object of a class
# template's specialization under it (#962) is the template: a class template is no value.
class Base:
    unit = "cm"

    def __init__(self) -> None:
        self.n = 0

    def describe(self) -> str:
        return type(self).unit + " " + str(self.n)


class T(Base):
    def __init__(self, v):
        super().__init__()
        self.v = v


print(Base().describe(), T(3).describe())
