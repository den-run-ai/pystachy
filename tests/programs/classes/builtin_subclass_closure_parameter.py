class Stack(list[int]):
    pass


class Mapping(dict[str, int]):
    pass


def make_check(label: str):
    def check(value: list[int]) -> bool:
        print(label)
        return isinstance(value, Stack)
    return check


check = make_check("comparison")


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        return check(other)


def make_keeper(seed: int):
    history = [seed]

    def keep(value: list[int] = [0], *, add: int = 4) -> list[int]:
        history.append(len(value))
        value.append(add)
        print(history)
        return value

    return keep


def make_dict_keeper(seed: str):
    key = seed

    def keep(value: dict[str, int]) -> dict[str, int]:
        value[key] = 7
        return value

    return keep


s = Stack([1])
print(Probe() == s)
keep = make_keeper(10)
other = make_keeper(20)
plain = [2]
copied = keep(s, add=3)
print(copied is s, isinstance(copied, Stack), copied)
print(keep(plain) is plain, plain)
first = keep()
second = keep()
print(first is second, first)
print(other(s) is s, s)
d = Mapping({"a": 1})
store = make_dict_keeper("b")
result = store(d)
print(result is d, isinstance(result, Mapping), result)
