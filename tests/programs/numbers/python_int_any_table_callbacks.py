# pystachy: dynamic-any
# pystachy: python-int
from typing import Any


class Key:
    def __init__(self, name: str, value: int) -> None:
        self.name = name
        self.value = value

    def __hash__(self) -> int:
        print("hash", self.name)
        return hash(self.value)

    def __eq__(self, other: Any) -> bool:
        print("eq", self.name, type(other).__name__, other)
        return other == self.value

    def __repr__(self) -> str:
        return self.name


wide = 2 ** 70
entries: dict[int, int] = {wide: wide + 1}
elements: set[int] = {wide}
key: Any = Key("present", wide)
absent: Any = Key("absent", wide + 1)
print(key in entries, entries[key], entries.get(key))
print(absent in entries, entries.get(absent, 5))
print(key in elements, absent in elements)
print(entries.setdefault(key, 8))
print(entries.pop(key))
print(entries.pop(absent, 8))
try:
    print(entries.pop(absent))
except KeyError as error:
    print("empty pop", str(error))
try:
    del entries[absent]
except KeyError as error:
    print("empty delete", str(error))
elements.discard(key)
elements.discard(absent)
try:
    elements.remove(absent)
except KeyError as error:
    print("remove", str(error))


class Change:
    def __init__(self, dictionary: dict[int, int], values: set[int]) -> None:
        self.dictionary = dictionary
        self.values = values
        self.calls = 0

    def __hash__(self) -> int:
        print("hash change")
        return hash(wide)

    def __eq__(self, other: Any) -> bool:
        print("eq change", self.calls, other)
        self.calls += 1
        if self.calls == 1:
            self.dictionary.clear()
            self.values.clear()
            for i in range(30):
                self.dictionary[i] = i
                self.values.add(i)
            self.dictionary[wide] = 99
            self.values.add(wide)
        return other == wide


entries[wide] = 7
elements.add(wide)
changing: Any = Change(entries, elements)
print("changed dict", entries[changing])
# A small table must grow during this lookup, independent of allocator reuse.
elements = {wide}
changing = Change(entries, elements)
print("changed set", changing in elements)


class Raises:
    def __hash__(self) -> int:
        print("hash raises")
        return hash(wide)

    def __eq__(self, other: Any) -> bool:
        print("eq raises", other)
        raise ValueError("query equality")


raising: Any = Raises()
try:
    print(raising in entries)
except ValueError as error:
    print(str(error))
try:
    print(raising in elements)
except ValueError as error:
    print(str(error))
print(entries[wide], wide in elements)


class Drops:
    def __init__(self, dictionary: dict[int, int], values: set[int], value: int) -> None:
        self.dictionary = dictionary
        self.values = values
        self.value = value

    def __hash__(self) -> int:
        return self.value

    def __eq__(self, other: Any) -> bool:
        print("drop", other)
        self.dictionary.pop(self.value, None)
        self.values.discard(self.value)
        return True


entries[0] = 3
elements.add(1)
zero: Any = Drops(entries, elements, 0)
one: Any = Drops(entries, elements, 1)
print("deleted zero", zero in entries)
print("deleted one", one in elements)


class Saved:
    def __init__(self) -> None:
        self.item: Any = None

    def __hash__(self) -> int:
        return hash(wide)

    def __eq__(self, other: Any) -> bool:
        self.item = other
        return True


saved = Saved()
saving: Any = saved
print("saved", saving in entries)
entries.clear()
garbage: list[Any] = []
for i in range(20):
    garbage.append([i, i + 1])
print("retained", saved.item, len(garbage))
