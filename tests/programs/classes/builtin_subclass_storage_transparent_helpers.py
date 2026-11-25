class Stack(list[int]):
    pass


def same(items):
    """Return the same storage."""
    return items


shared: list[list[int]] = []


def get_shared():
    return shared


global_get = get_shared


def add_shadowed(value):
    shared = get_shared()
    shared.append(value)
    print(shared is get_shared(), shared[-1] is value)


def use(value):
    def list(items):
        return items
    original = [[0]]
    view = list(items=original)
    alias = same(view)
    alias.append(value)
    print(alias is original, view is original, alias[1] is value)
    print(isinstance(original[1], Stack), len(original[1]) == 1)

    shared = [[-7]]
    supplied = global_get()
    supplied.append(value)
    print(supplied is get_shared(), shared, supplied[0] is value)
    original[1].append(5)
    print(value, supplied[0])


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        use(other)
        add_shadowed(other)
        return isinstance(other, Stack)


s = Stack([1])
print(Probe() == s)
print(shared[0] is s, isinstance(shared[0], Stack), shared)
