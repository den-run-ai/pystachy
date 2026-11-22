# A subclass of a class template whose own __init__ is a class template too (#962): each of its
# specializations derives from the specialization of Base that its super().__init__(...) makes,
# for the types of its own arguments, and is made before any code is compiled (code that makes
# one first is compiled again, with it known from the start).
class Base:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Child(Base):
    def __init__(self, value):
        super().__init__(value)


print(Child(1).get())
print(Child("one").get(), Base(2.5).get())
