class Stack(list[int]):
    pass


seen = []
alias = seen


class Probe:
    def __eq__(self, other):
        seen.append(other)
        return isinstance(other, Stack)


s = Stack()
s.append(1)
print(Probe() == s)
alias.insert(1, [2])
s.append(3)
print(type(alias[0]).__name__, alias[0] is s, alias is seen)
print(seen)
alias[1] = s
print(type(seen[1]).__name__, seen[0] is seen[1])
