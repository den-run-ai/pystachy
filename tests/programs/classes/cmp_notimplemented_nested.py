# What one method returns is kept apart from what the comparisons it runs return: a method that
# compares objects whose methods return NotImplemented, and then returns a result of its own;
# and one that returns NotImplemented after a comparison that gave a result.
class Inner:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        print("Inner.__eq__", self.n)
        if not isinstance(other, Inner) or other.n < 0 or self.n < 0:
            return NotImplemented
        return self.n == other.n


class Outer:
    def __init__(self, a: int, b: int) -> None:
        self.a = Inner(a)
        self.b = Inner(b)

    def __eq__(self, other):
        print("Outer.__eq__")
        if not isinstance(other, Outer):
            return NotImplemented
        # (a negative Inner declines both ways: identity then decides, and this method goes on)
        return self.a == other.a or self.b == other.b

    def __lt__(self, other):
        print("Outer.__lt__")
        if not isinstance(other, Outer):
            return NotImplemented
        if self.a == other.a:
            return NotImplemented  # (after a comparison that gave a result)
        return self.b.n < other.b.n


xs = [Outer(-1, 2), Outer(-1, 2), Outer(-1, 3), Outer(4, 5), Outer(4, 6)]
print(xs[0] == xs[1])
print(xs[0] == xs[2])
print(xs[0] != xs[2])
print(xs[0] < xs[3])
for i, j in [(3, 4), (4, 3)]:
    try:
        print(xs[i] < xs[j])
    except TypeError as e:
        print("TypeError", e)
