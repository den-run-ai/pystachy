# type(x).__name__, __qualname__ and __module__, and x.__class__.__name__ (#486): a constant
# where the static type decides, else the name in the record of the exact class (class tag,
# then union tag)
class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(x={self.x})"


class Cat:
    def speak(self) -> str:
        return "meow"


class Dog:
    def speak(self) -> str:
        return "woof"


class Animal:
    def kind(self) -> str:
        return type(self).__name__


class Bird(Animal):
    pass


class Parrot(Bird):
    pass


class Box:
    def __init__(self, v) -> None:
        self.v = v


class Err(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.code})"


def name_of(o) -> str:
    return type(o).__name__


p = Point(1)
print(type(p).__name__, p.__class__.__name__, type(p).__qualname__, type(p).__module__)
print(repr(p), [p])
pets: list[Cat | Dog] = [Cat(), Dog()]
for pet in pets:
    print(type(pet).__name__, pet.__class__.__qualname__, pet.speak())
zoo: list[Animal] = [Animal(), Bird(), Parrot()]
for a in zoo:
    print(type(a).__name__, a.__class__.__name__, a.kind())
print(type(Box(1)).__name__, type(Box("s")).__name__)
print(name_of(1), name_of(2.5), name_of(True), name_of("s"), name_of(None), name_of([1]), name_of({"a": 1}), name_of((1, "a")), name_of({1}), name_of(frozenset({1})), name_of(Cat()))
print(type(1).__module__, type(None).__qualname__, type([1, 2]).__name__, name_of(b"x"), type(b"x") is bytes, dir(b"")[-2:])
u: int | str = "a"
print(type(u).__name__)
u = 3
print(type(u).__name__)
maybe: Point | None = None
print(type(maybe).__name__)
maybe = Point(2)
print(type(maybe).__name__)
try:
    raise Err(7)
except Err as e:
    print(type(e).__name__, e.__class__.__name__, repr(e))
