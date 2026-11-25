class Stack(list[int]):
    pass

class Store:
    seen: list[list[int]] = [[8]]

store = Store()
original: list[list[int]] = Store.seen
Store.seen = [[0]]
alias = store.seen = [[3]]

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        store.seen.append(other)
        return isinstance(other, Stack)

value = Stack([1])
print(Probe() == value)
print(alias is store.seen, alias[-1] is value)
print(original, Store.seen, alias[0])
