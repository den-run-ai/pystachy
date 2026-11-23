# A class method of a class template called through a location typed by a class under the
# template that another class derives from, which holds an object of that deriving class. The
# call is not dispatched on the object's class, so with the classes' own copies of the method
# cls would be the location's class, Mid, where CPython's is Deep. The program is compiled
# without the copies, as before they were made (#1744): cls is the template there, whose tag
# Deep's is again, and the program prints what CPython prints
class Style:
    tag = "plain"

    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def kind(cls) -> str:
        return cls.tag


class Mid(Style):
    tag = "mid"


class Deep(Mid):
    tag = "plain"


xs = [Mid(1)]
xs[0] = Deep(2)
print(xs[0].kind())
