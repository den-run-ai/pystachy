# error: expected list[int], got Stack
class Stack(list[int]):
    pass


class Store:
    seen: list[list[int]] = []


store = Store()


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return isinstance(other, Stack)


print(Probe() == Stack([1]))
