class Stack(list[int]):
    pass


seen: list[list[int]] = []


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        seen.append(other)
        return isinstance(other, Stack)


s = Stack()
s.append(1)
print(Probe() == s)
seen.append([2])
s.append(3)
print(type(seen[0]).__name__, seen[0] is s)
print(seen)


def read(values: list[list[int]]):
    print(type(values[0]).__name__, values[0] is s)
    return values


print(read(seen) is seen)
