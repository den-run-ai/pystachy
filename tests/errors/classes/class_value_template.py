# error: class 'T' cannot be used as a value: it is a class template
# a class whose __init__ has a parameter without an annotation is a template: its objects are
# its specializations', which a class object cannot choose between (#7)
class T:
    def __init__(self, v):
        self.v = v


def make() -> int:
    k = T
    return k(1).v


print(make())
