class Stack(list[int]):
    pass


class Queue(list[int]):
    pass


seen = []


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        seen.append(other)
        return isinstance(other, Stack) or isinstance(other, Queue)


s = Stack([1, 2])
q = Queue([3, 4])
print(Probe() == s, Probe() == q)
seen.append([5, 6])
for row in seen:
    print(type(row).__name__, list(row), row[0], row[-1], row[1:])
    row[0] += 10
    row[1] = 20
    row.append(30)
    del row[1]
    a, b = row
    print(a, b, [x for x in row], [*row])
    row[:] = [7, 8]
    row[1:] += [9]
    del row[::2]
print(type(seen[0]).__name__, seen[0] is s, seen[1] is q)
print(s, q, seen)
