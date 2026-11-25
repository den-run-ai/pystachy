# A global alias's field receiver is resolved in its module, not in the caller's locals.
class Stack(list[int]):
    pass


class Store:
    def __init__(self):
        self.seen: list[list[int]] = []


class Other:
    def __init__(self):
        self.seen = 9


source = Store()
alias: list[list[int]] = source.seen


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        source = Other()
        alias.append(other)
        print(source.seen)
        return isinstance(other, Stack)


s = Stack([8])
print(Probe() == s)
print(type(source.seen[0]).__name__, source.seen[0] is s, alias is source.seen)
