# An annotated alias may store comparison operands even when only contents are observed.
# This already matched CPython before class-preserving shared storage (#409).
class Stack(list[int]):
    pass

seen: list[list[int]] = []
alias: list[list[int]] = seen

class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        alias.append(other)
        return len(other) == 1

s = Stack([1])
print(Probe() == s)
print(seen[0])
