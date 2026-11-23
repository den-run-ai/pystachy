# A subclass of a class template whose own __init__ is a class template too (#962), which assigns
# through its base's property: the setter runs, also in the specialization that is made where the
# classes are declared, and name is no field of Dog's own.
class Animal:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, v):
        self._name = v


class Dog(Animal):
    def __init__(self, name, loud):
        super().__init__(name)
        self.name = name + "!"
        self.loud = loud


d = Dog("rex", True)
print(d.name, d._name, d.loud)
d.name = "max"
for a in [Animal("cat"), d]:
    print(a.name, isinstance(a, Dog))
