# error: a subclass of a class template whose own __init__ is a class template, Pet, is not supported for an argument of type Owner[str] (an object of a class template's specialization, a lambda, a nested function or a bound method)
# Each specialization of a subclass whose own __init__ is a class template is made where the
# classes are declared, before any code is compiled, and so for the types that the declarations
# know: not an object of a class template's specialization, which only compiled code makes.
class Owner:
    def __init__(self, name):
        self.name = name


class Animal:
    def __init__(self, name):
        self.name = name


class Pet(Animal):
    def __init__(self, name, owner):
        super().__init__(name)
        self.owner = owner


print(Pet("rex", Owner("ann")).owner.name)
