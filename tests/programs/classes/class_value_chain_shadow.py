# pystachy: dynamic-any
seen: list[int] = []

class Shadow:
    def __init__(self, k: int) -> None:
        self.k = k

    def again(self) -> "Shadow":
        seen.append(1)
        return self

    def __class__(self, value: int) -> int:
        seen.append(3)
        return value + self.k

def arg() -> int:
    seen.append(2)
    return 7

s = Shadow(4)
print(s.again().__class__(arg()), seen)
