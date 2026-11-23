# Values of a template hierarchy's classes chosen at run time: the arms of a conditional
# expression, a comprehension's items, `or`, a function's returns, and their narrowing by
# isinstance() tests, whose type is the specialization the classes derive from (#962).
class Animal:
    def __init__(self, name, legs=4):
        self.name = name
        self.legs = legs

    def sound(self) -> str:
        return "..."


class Dog(Animal):
    def sound(self) -> str:
        return "woof"


class Bird(Animal):
    def __init__(self, name: str) -> None:
        super().__init__(name, 2)

    def sound(self) -> str:
        return "tweet"


def make(i: int):
    if i % 3 == 0:
        return Animal("generic")
    if i % 3 == 1:
        return Dog("rex")
    return Bird("tweety")


def describe(a) -> str:
    if isinstance(a, Bird):
        return "bird " + a.name + " " + str(a.legs)
    if isinstance(a, Dog):
        return "dog " + a.name
    return "animal " + a.name


for i in range(4):
    a = Dog("d" + str(i)) if i % 2 == 0 else Animal("a" + str(i))
    print(a.name, a.sound(), a.legs)
zoo = [make(i) for i in range(5)]
for z in zoo:
    print(z.name, z.sound(), z.legs, describe(z))
first = zoo[0] or Dog("fallback")
print(first.sound(), sum([z.legs for z in zoo]))
