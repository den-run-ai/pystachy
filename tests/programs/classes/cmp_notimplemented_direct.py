# Methods that return NotImplemented for another class, called directly with new objects: the
# class of each is known, which decides the test, so that no call returns NotImplemented.
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        if not isinstance(other, V):
            return NotImplemented
        return self.n == other.n

    def __lt__(self, other):
        if not isinstance(other, V):
            return NotImplemented
        return self.n < other.n


print(V(1).__lt__(V(2)), V(2).__lt__(V(1)), V(1).__eq__(V(1)), V(1).__eq__(V(2)))
print(V(1) == V(1), V(1) != V(1), V(1) < V(2), V(2) > V(1))
