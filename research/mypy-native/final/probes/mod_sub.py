from typing import Final
X: Final[int] = 3
D: Final[dict[str, int]] = {"a": 1}
L: Final[list[int]] = []
L.append(2)
print(X, D, L)
