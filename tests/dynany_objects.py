# pystachy: dynamic-any
# Objects of the program's classes as Any values: fields annotated Any change type, attributes
# and methods are found by the object's class at run time, objects with __eq__ and __hash__
# are dict keys.
from typing import Any


class Box:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.tag: Any = None

    def get(self) -> Any:
        return self.value

    def put(self, v: Any) -> None:
        self.value = v

    def __repr__(self) -> str:
        return f"Box({self.value!r})"


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Point) and self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"

    def norm1(self) -> int:
        return abs(self.x) + abs(self.y)


class Animal:
    def __init__(self, name: str) -> None:
        self.name = name

    def speak(self) -> str:
        return self.name + " makes a sound"

    def __repr__(self) -> str:
        return type(self).__name__ + "(" + repr(self.name) + ")"


class Dog(Animal):
    def speak(self) -> str:
        return self.name + " barks"


b = Box(1)
print(b.get(), b)
b.put("now a str")
print(b.get(), b)
b.put([1, 2])
b.value.append(3)
print(b, b.value)
b.tag = Point(1, 2)
print(b.tag, b.tag.x)
things: list[Any] = [Box(1), Point(3, 4), Dog("rex"), Animal("cat"), 5, "s"]
for t in things:
    print(type(t).__name__, repr(t))
for t in things:
    if isinstance(t, Animal):
        print(t.speak())
any_obj: Any = things[1]
print(any_obj.norm1(), any_obj.x + any_obj.y)
any_obj.x = 10
print(things[1])
dog: Any = things[2]
print(dog.speak(), dog.name)
seen: dict[Any, Any] = {}
seen[Point(1, 2)] = "a"
seen[Point(1, 2)] = "b"
seen[Point(2, 1)] = "c"
print(seen, len(seen))
print(Point(1, 2) in seen, Point(5, 5) in seen)
p: Any = Point(1, 2)
q: Any = Point(1, 2)
print(p == q, p != q, p is q, p is p)
bx: Any = Box(7)
print(bx.get(), bx.value)
bx.value = "changed"
print(bx.get())
