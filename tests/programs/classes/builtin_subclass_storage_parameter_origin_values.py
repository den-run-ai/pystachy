# Value-only observations of the same storage must remain supported.
class Stack(list[int]):
    pass
seen: list[list[int]] = []

def store(where: list[list[int]], value):
    where.append(value)

def get_seen():
    return seen

class Probe:

    def __eq__(self, other):
        if other is None:
            return False
        store(get_seen(), other)
        return len(other) == 1
s = Stack([1])
print(Probe() == s)
