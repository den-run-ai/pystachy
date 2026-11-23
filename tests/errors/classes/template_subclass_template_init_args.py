# error: the types of the arguments of super().__init__(...) in Child.__init__ must be known from the types of its parameters
# A subclass whose own __init__ is a class template derives from the specialization that its
# super().__init__(...) makes, for the types that its parameters' types give its arguments, before
# the code that makes them is compiled: not a call of a function without a return annotation.
class Base:
    def __init__(self, value):
        self.value = value


def make(n):
    return [n, n]


class Child(Base):
    def __init__(self, n):
        super().__init__(make(n))


print(Child(2).value)
