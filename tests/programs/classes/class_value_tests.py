# isinstance() and issubclass() take a class object held as a value (#7): an object's class, or a
# class object's class, is tested against it. A value of another type is an instance of no class
# of the program, and every class derives from object
class Animal:
    pass


class Dog(Animal):
    pass


class Puppy(Dog):
    pass


class Cat(Animal):
    pass


class Stone:
    pass


def check(x: Animal, kind: type[Animal]) -> bool:
    return isinstance(x, kind)


def under(a: type[Animal], b: type[Animal]) -> bool:
    return issubclass(a, b)


def others(x: int, s: str, k: type[Animal]) -> tuple[bool, bool, bool]:
    return (isinstance(x, k), isinstance(s, k), isinstance(None, k))


def bases(k: type[Animal]) -> tuple[bool, bool, bool, bool]:
    return (issubclass(k, object), issubclass(k, KeyError), issubclass(k, int), issubclass(k, Animal))


def member(x: Animal | Stone | None, k: type[Animal]) -> list[bool]:
    return [isinstance(x, k), isinstance(x, type(None))]


def scalar(x: int | str | None, k: type[Animal]) -> bool:
    return isinstance(x, k)


def which(n: int) -> type[Animal]:
    return Animal if n == 0 else Dog if n == 1 else Cat


pets: list[Animal] = [Animal(), Dog(), Puppy(), Cat()]
kinds: list[type[Animal]] = [Animal, Dog, Puppy, Cat]
for p in pets:
    print(type(p).__name__, [check(p, k) for k in kinds])
for a in kinds:
    print(a.__name__, [under(a, b) for b in kinds], issubclass(a, Dog), issubclass(a, Animal), issubclass(a, Puppy))
d: Dog = Puppy()
print(isinstance(d, type(pets[1])), isinstance(pets[1], type(d)), issubclass(type(d), Dog), issubclass(type(d), Cat))
print([k.__name__ for k in kinds if issubclass(k, Dog)], [which(i).__name__ for i in range(3)])
print(others(1, "s", Dog), bases(Animal), bases(Puppy))
print(member(Dog(), Animal), member(Dog(), Cat), member(Stone(), Animal), member(None, Animal))
print(scalar(1, Dog), scalar("s", Dog), scalar(None, Dog))
