from typing import Final
def f(n: int) -> int:
    k: Final = 3
    m: Final[int] = n * 2
    t: Final = [n, k]
    return k + m + len(t)
print(f(4))
