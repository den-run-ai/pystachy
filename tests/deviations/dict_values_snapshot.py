# Documented deviation: d.values() is a list snapshot, so `in` and max() over it do not notice
# an __eq__ or __lt__ that inserts into the dict. CPython's view does, and raises
# RuntimeError: dictionary changed size during iteration at the first insertion.
class Q:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, o: "Q") -> bool:
        X[100 + len(X)] = Q(0)
        return self.n == o.n

    def __lt__(self, o: "Q") -> bool:
        X[100 + len(X)] = Q(0)
        return self.n < o.n


X: dict[int, Q] = {1: Q(1), 2: Q(2), 3: Q(3)}
print(max(X.values()).n, len(X))
print(Q(2) in X.values(), len(X))
