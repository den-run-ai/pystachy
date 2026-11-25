# This annotated-helper program already matched CPython before retaining stored subclasses.
class Stack(list[int]):
    pass

seen: list[list[int]] = []

def store(where: list[list[int]], value):
    where.append(value)

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store(seen, other)
        return len(other) == 1

s = Stack([1])
print(Probe() == s)
