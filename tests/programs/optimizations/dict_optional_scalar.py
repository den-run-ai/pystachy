"""Private optional dictionary reads preserve their scalar snapshots."""

def read_int(values: dict[str, int], key: str) -> int:
    value = values.get(key)
    if value is None:
        return -101
    return value + 7


def read_float(values: dict[str, float], key: str) -> None:
    value = values.get(key)
    if value is None:
        print("missing")
    else:
        print(value.hex())


def read_bool(values: dict[str, bool], key: str) -> None:
    value = values.get(key)
    if value is None:
        print("missing")
    else:
        print(value, not value)


def snapshot(values: dict[str, int], key: str) -> int:
    value = values.get(key)
    values.clear()
    values[key] = 909
    if value is None:
        return -1
    return value + 1


def key_once() -> str:
    print("key")
    return "hit"


def default_once() -> None:
    print("default")


def side_effects(values: dict[str, int]) -> int:
    value = values.get(key_once(), default_once())
    if value is None:
        return -1
    return value + 1


class Key:
    def __init__(self, number: int):
        self.number = number

    def __hash__(self) -> int:
        print("hash", self.number)
        if self.number == 99:
            raise ValueError("key hash")
        return 0

    def __eq__(self, other: "Key") -> bool:
        print("equal", self.number, other.number)
        return self.number == other.number


def read_key(values: dict[Key, int], key: Key) -> int:
    value = values.get(key)
    if value is None:
        return -1
    return value + 1


def looping(values: dict[int, int]) -> int:
    total = 0
    for key in range(9):
        value = values.get(key)
        if value is None:
            total -= 2
        else:
            total += value
    return total


for key in ["zero", "negative", "hit", "missing"]:
    print(read_int({"zero": 0, "negative": -7, "hit": 12}, key))
print(read_int({}, "missing"))
for key in ["zero", "negative_zero", "nan", "inf", "negative_inf", "missing"]:
    read_float({"zero": 0.0, "negative_zero": -0.0, "nan": float("nan"),
                "inf": float("inf"), "negative_inf": -float("inf")}, key)
for key in ["false", "true", "missing"]:
    read_bool({"false": False, "true": True}, key)
print(snapshot({"hit": 12}, "hit"), snapshot({}, "hit"))
print(side_effects({"hit": 25}), side_effects({}))
values = {Key(1): 10, Key(2): 20}
print(read_key(values, Key(2)))
print(read_key(values, Key(3)))
try:
    print(read_key(values, Key(99)))
except ValueError as error:
    print(str(error))
print(looping({0: 0, 1: -1, 3: 7, 8: 10}))
