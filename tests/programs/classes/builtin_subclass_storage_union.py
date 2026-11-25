class Stack(list[int]):
    pass


class Queue(list[int]):
    def __repr__(self) -> str:
        return "Queue!"


def show(value: Stack | Queue | list[int]) -> None:
    print(type(value).__name__, repr(value), len(value), bool(value))
    print(isinstance(value, list), isinstance(value, Stack), value == [1])
    value.append(7)
    print(repr(value))


s = Stack([1])
q = Queue([1])
show(s)
show(q)
show([1])
items: list[Stack | Queue | list[int]] = [s, q, [1, 7]]
print(items)
print(items == [[1, 7], [1, 7], [1, 7]])
print(items[0] is s, items[1] is q)
