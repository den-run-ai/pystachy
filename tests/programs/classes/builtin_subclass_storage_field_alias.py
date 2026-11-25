# Every instance allocates tagged items before any annotated alias reads its field.
class Stack(list[int]):
    pass


class Store:
    def __init__(self):
        self.seen: list[list[int]] = []


class Other:
    def __init__(self):
        self.seen = 17


first = Store()
second = Store()
unrelated = Other()
alias: list[list[int]] = first.seen


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        alias.append(other)
        return isinstance(other, Stack)


s = Stack([1])
print(Probe() == s)
print(alias is first.seen, first.seen is second.seen, len(second.seen), unrelated.seen)
print(type(alias[0]).__name__, alias[0] is s)
s.append(2)
print(first.seen[0], alias[0])
second.seen.append([3])
print(first.seen, second.seen)


def read_after() -> None:
    local_alias: list[list[int]] = first.seen
    local_alias.append([8])
    local_alias[0].append(9)
    print(local_alias is alias, local_alias[0] is s, type(local_alias[0]).__name__)


read_after()
print(s, first.seen, second.seen)
