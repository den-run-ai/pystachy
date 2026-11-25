# Value-only observations of the same storage must remain supported.
class Stack(list[int]):
    pass

def store(value):

    def list(items):
        return items
    original = [[0]]
    seen = list(original)
    seen.append(value)
    print(len(original[1]) == 1)

class Probe:

    def __eq__(self, other):
        if other is None:
            return False
        store(other)
        return len(other) == 1
s = Stack([1])
print(Probe() == s)
