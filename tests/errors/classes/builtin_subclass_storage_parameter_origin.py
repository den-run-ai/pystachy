# error: an object of a class that derives from list is not stored or passed as a list yet, where it would lose its class
# A helper cannot reinterpret an argument whose allocation origin is unknown.
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
        return isinstance(other, Stack)

s = Stack([1])
print(Probe() == s)
