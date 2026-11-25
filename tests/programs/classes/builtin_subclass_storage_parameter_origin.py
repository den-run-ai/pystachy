# The getter returns the module binding itself. Its caller's storage request
# follows that proven identity back to the original allocation.
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
