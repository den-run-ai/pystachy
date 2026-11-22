# isinstance() of a value of object with a class of the program or a builtin type, which narrows it
# as an if, an early return, a continue or a while narrows a union: to the class, to bool, int
# (whose test a bool passes too, keeping its own repr), float, str, bytes or type; a container's
# test (list, dict, tuple, set) narrows nothing, as its items' types are not known
class Animal:
    def __init__(self, name: str) -> None:
        self.name = name

    def speak(self) -> str:
        return self.name + " makes a sound"


class Dog(Animal):
    def speak(self) -> str:
        return self.name + " barks"


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def describe(x: object) -> str:
    if isinstance(x, bool):
        return "bool " + str(not x)
    if isinstance(x, int):
        return "int " + str(x * 2)
    if isinstance(x, float):
        return "float " + str(x / 2)
    if isinstance(x, str):
        return "str " + x.upper() + " " + str(len(x))
    if isinstance(x, bytes):
        return "bytes " + str(len(x)) + " " + str(x[0])
    if isinstance(x, Box):
        return "Box " + str(x.v + 1)
    if isinstance(x, Animal):
        return "Animal " + x.speak()
    if isinstance(x, list):
        return "list " + repr(x)
    if isinstance(x, dict):
        return "dict " + str(x)
    if isinstance(x, tuple):
        return "tuple " + format(x)
    if isinstance(x, set):
        return "set " + f"{x}"
    if isinstance(x, type):
        return "type " + x.__name__
    if x is None:
        return "None"
    return "other " + repr(x)


def first_int(xs: list[object]) -> int:
    for x in xs:
        if not isinstance(x, int):
            continue
        return x + 100
    return -1


def early(x: object) -> str:
    if not isinstance(x, str):
        return "not a str"
    return x + "!"


def ints_only(x: object) -> int:
    if isinstance(x, int) and not isinstance(x, bool):
        return x
    return 0


def main() -> None:
    xs: list[object] = [True, 7, 2.5, "abc", b"xy", Box(4), Dog("rex"), Animal("cat"), [1, 2], {"a": 1}, (1, 2, 3), {9}, Box, None, frozenset([1])]
    for x in xs:
        print(describe(x))
    print(isinstance(xs[0], int), isinstance(xs[1], bool), isinstance(xs[2], (int, float)), isinstance(xs[6], Animal), isinstance(xs[7], Dog))
    print(isinstance(xs[13], object), isinstance(xs[3], (bytes, str)), isinstance(xs[12], type), isinstance(xs[14], set), isinstance(xs[14], frozenset))
    print(first_int(xs), first_int(["a", None]), early("hi"), early(3), ints_only(True), ints_only(5), ints_only("5"))
    y: object = 41
    if isinstance(y, int):
        y = y + 1
    print(y)
    z: object = "a"
    while isinstance(z, str) and len(z) < 4:
        z = z + "b"
    print(z)
    w: object = Dog("fido")
    print(w.speak() if isinstance(w, Animal) else "no", w.name if isinstance(w, Dog) else "no")


main()
