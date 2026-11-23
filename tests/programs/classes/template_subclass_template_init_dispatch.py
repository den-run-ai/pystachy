# A subclass of a class template whose own __init__ is a class template too (#962): each of its
# specializations derives from the specialization of the template that its super().__init__(...)
# makes, for the types of its own arguments, and is made before any code is compiled, so that a
# call through a value of the base's type selects the object's override. speak_all() is compiled
# for a list of Animal("cat")'s class before the program makes its first Dog, which the second
# call passes it. Puppy, without an __init__ of its own, has one specialization with each of
# Dog's; Corgi derives from the one its super().__init__("corgi", 2) makes; Dog(7, "x") derives
# from Animal's for an int, of a hierarchy of its own.
class Animal:
    def __init__(self, name):
        self.name = name

    def sound(self):
        return "..."

    def describe(self):
        return self.name + " says " + self.sound()


class Dog(Animal):
    def __init__(self, name, loud):
        super().__init__(name)
        self.loud = loud

    def sound(self):
        return "WOOF" if self.loud else "woof"


class Puppy(Dog):
    def sound(self):
        return "yip " + super().sound()


class Corgi(Dog):
    def __init__(self) -> None:
        super().__init__("corgi", 2)


def speak_all(xs):
    for x in xs:
        print(x.describe(), isinstance(x, Dog), isinstance(x, Puppy), isinstance(x, Animal))


a = Animal("cat")
speak_all([a])
d = Dog("rex", True)
q = Dog("max", 0)
p = Puppy("bit", False)
c = Corgi()
speak_all([a, d, q, p, c])
print(d.loud, q.loud, c.loud, p.name)
n = Dog(7, "x")
print(n.name + 1, n.loud, n.sound(), isinstance(n, Animal))
