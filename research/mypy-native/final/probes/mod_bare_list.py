from typing import Final
X: Final = [1, 2]
D: Final = {"a": 1}
T: Final = (1, "a")
S: Final = frozenset({1, 2})
print(X, D, T, sorted(S))
