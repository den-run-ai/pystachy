# pystachy: dynamic-any
# Exact-int probes of Any dictionaries keep numeric equality, the original query
# object, and generic lookup's restart/error behavior when a comparison runs code.
from typing import Any


numbers: dict[Any, Any] = {1.0: "float", False: "false"}
print("mixed", numbers[int("1")], numbers[int("0")])
numbers[True] = "bool"
numbers[1] = "int"
print("one key", len(numbers), numbers[1.0], numbers[True])
numbers[-1] = "minus one"
numbers[-2] = "minus two"
print("collision", numbers[int("-1")], numbers[int("-2")], numbers.get(-3, "missing"))

large: dict[Any, Any] = {float(9007199254740992): "exact float"}
large[9007199254740993] = "next int"
large[9223372036854775807] = "maximum"
large[-9223372036854775808] = "minimum"
print("large", len(large), large[int("9007199254740992")], large[int("9007199254740993")])
print("bounds", large[int("9223372036854775807")], large[int("-9223372036854775808")])
print("rounded", int("9007199254740994") in large, float(9223372036854775807) in large)

sparse: dict[Any, Any] = {}
for i in range(80):
    sparse[i] = i * 3
for i in range(0, 80, 2):
    del sparse[i]
print("holes", len(sparse), sparse.get(22, -1), sparse[23], 80 in sparse)
for i in range(0, 80, 2):
    sparse[i] = i * 5
print("refilled", len(sparse), sparse[22], sparse.setdefault(23, -1), sparse.setdefault(80, 400))
print("pop", sparse.pop(24), sparse.pop(24, -1), sparse.get(80), len(sparse))


class Key:
    def __init__(self, value: int, table: dict[Any, Any]) -> None:
        self.value = value
        self.table = table
        self.saved: Any = None
        self.mode = -1

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: Any) -> bool:
        if other == self.value:
            self.saved = other
        mode = self.mode
        self.mode = -1
        if mode == 0:
            self.table.clear()
        elif mode == 1:
            for i in range(64):
                self.table[i] = i
        elif mode == 2:
            del self.table[self]
            self.table[other] = "replacement"
        elif mode == 3:
            raise ValueError("comparison callback")
        # Keep the query object alive through allocations inside the callback.
        for i in range(4):
            garbage: list[Any] = [int("2345"), str(i), [i, other]]
            if len(garbage) != 3:
                print("bad garbage")
        return other == self.value


def lookup(mode: int) -> None:
    table: dict[Any, Any] = {}
    # This unequal int shares hash(1000), so the exact-int path probes an int
    # before falling back to the custom key. It must not recreate the query box.
    table[2305843009213694951] = "collision"
    key = Key(1000, table)
    table[key] = "custom"
    query: Any = int("1000")
    alias: Any = query
    key.mode = mode
    try:
        print("lookup", mode, table.get(query, "missing"), len(table))
    except ValueError as error:
        print("lookup", mode, type(error).__name__, str(error), len(table))
    print("query", key.saved is query, key.saved is alias, id(key.saved) == id(alias))
    query = None
    for i in range(8):
        garbage: list[Any] = [int("1000"), str(i), [i]]
        if len(garbage) != 3:
            print("bad garbage")
    print("retained", key.saved, key.saved is alias)


for mode in range(-1, 4):
    lookup(mode)


class HoleFiller:
    def __init__(self, table: dict[Any, Any]) -> None:
        self.table = table
        self.armed = False

    def __hash__(self) -> int:
        return 1000

    def __eq__(self, other: Any) -> bool:
        if self.armed:
            self.armed = False
            # Reuse the earlier deleted probe slot without resizing the table.
            # The outer insertion must choose another slot after this callback.
            self.table[4611686018427388902] = "filled"
        return False


for operation in range(2):
    holes: dict[Any, Any] = {}
    holes[2305843009213694951] = "deleted"
    filler = HoleFiller(holes)
    holes[filler] = "custom"
    del holes[2305843009213694951]
    filler.armed = True
    query: Any = int("1000")
    if operation == 0:
        holes[query] = "query"
    else:
        print("default", holes.setdefault(query, "query"))
    print("filled hole", operation, len(holes), holes.get(4611686018427388902, "missing"),
          holes.get(query, "missing"), 2305843009213694951 in holes)
    print("values", list(holes.values()))
