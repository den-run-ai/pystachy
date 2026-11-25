# error: expected list[int], got Stack
# A user function named list may return an existing container. It is not the
# builtin allocation whose new item representation can be chosen independently.
class Stack(list[int]):
    pass


def store(value):
    def list(items):
        return items
    original = [[0]]
    seen = list(original)
    seen.append(value)
    print(isinstance(original[1], Stack))


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store(other)
        return isinstance(other, Stack)


s = Stack([1])
print(Probe() == s)
