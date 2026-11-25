class Stack(list[int]):
    pass


original = [[0]]
seen = list(original)
alias = seen
from_display = list([[9]])


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        seen.append(other)
        from_display.append(other)
        return isinstance(other, Stack)


s = Stack([1])
print(Probe() == s)
print(original, seen, from_display)
print(original is seen, original[0] is seen[0], seen[1] is s)
print(alias is seen, alias[1] is s, from_display[1] is s)
print(isinstance(seen[1], Stack), isinstance(from_display[1], Stack))
original[0].append(3)
print(seen)
