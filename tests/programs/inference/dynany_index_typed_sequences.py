# pystachy: dynamic-any
# An Any value as the index of a typed list, str, tuple or bytes and as an argument of range():
# no annotation is checked there, so CPython's index protocol decides. An int is the index, a
# bool is 0 or 1, and an object is asked for its __index__(), once for a read, a store or a
# deletion and twice for an augmented assignment. Any other value raises the sequence's
# TypeError, which names the value's type. A sequence that is None raises before the object
# is asked.
from typing import Any


class Index:
    def __init__(self, label: str, value: int) -> None:
        self.label = label
        self.value = value

    def __index__(self) -> int:
        print("index", self.label)
        return self.value


class BadIndex:
    def __index__(self) -> Any:
        print("bad index")
        return 1.5


class Raising:
    def __index__(self) -> int:
        raise ValueError("index failed")


class Plain:
    pass


numbers: list[int] = [10, 20, 30, 40]
words: list[str] = ["p", "q", "r", "s"]
text: str = "abcd"
fixed: tuple[int, ...] = (1, 2, 3, 4)
data: bytes = b"wxyz"


def read(label: str, key: Any) -> None:
    try:
        print(label, numbers[key], words[key], text[key], fixed[key], data[key])
    except TypeError as error:
        print(label, "TypeError:", error)
    except ValueError as error:
        print(label, "ValueError:", error)
    except IndexError as error:
        print(label, "IndexError:", error)


def each(label: str, key: Any) -> None:
    for name in ["list", "str", "tuple", "bytes"]:
        try:
            if name == "list":
                print(words[key])
            elif name == "str":
                print(text[key])
            elif name == "tuple":
                print(fixed[key])
            else:
                print(data[key])
        except TypeError as error:
            print(label, name, "TypeError:", error)


read("int", 2)
read("negative", -1)
read("true", True)
read("false", False)
read("object", Index("one", 1))
read("last", Index("minus one", -1))
read("far", Index("nine", 9))
read("bad", BadIndex())
read("raising", Raising())
each("str", "1")
each("float", 1.0)
each("none", None)
each("plain", Plain())
each("list", [1])

key: Any = Index("store", 1)
numbers[key] = 21
print(numbers)
numbers[key] += 1
print(numbers)
flag: Any = True
numbers[flag] += 5
print(numbers)
del numbers[key]
print(numbers)
del numbers[flag]
print(numbers)
for wrong in ["x", 2.5, None]:
    other: Any = wrong
    try:
        numbers[other] = 0
    except TypeError as error:
        print("store TypeError:", error)
    try:
        numbers[other] += 1
    except TypeError as error:
        print("augmented TypeError:", error)
    try:
        del numbers[other]
    except TypeError as error:
        print("del TypeError:", error)
print(numbers)

start: Any = Index("start", 1)
stop: Any = Index("stop", 7)
step: Any = Index("step", 2)
print(list(range(stop)), list(range(start, stop)), list(range(start, stop, step)))
print(list(range(flag, stop)))
for wrong in ["x", 2.5, None]:
    other = wrong
    try:
        print(list(range(other)))
    except TypeError as error:
        print("range TypeError:", error)

missing: list[int] | None = None
if len(words) > 9:
    missing = [1]
try:
    print(missing[key])
except TypeError as error:
    print("TypeError:", error)
try:
    missing[key] = 1
except TypeError as error:
    print("TypeError:", error)
