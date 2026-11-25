class Stack(list[int]):
    pass


values: list[list[int]] = []


class Store:
    seen: list[list[int]] = values


store = Store()


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return len(other) == 1


print(Probe() == Stack([1]))
