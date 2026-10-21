# an empty [] or {} left of `in` takes its type from what the object's __contains__ takes, or
# from the items its __iter__ steps through
from typing import Iterator


class C:
    def __contains__(self, k: list[int]) -> bool:
        return not k


class D:
    def __contains__(self, k: dict[str, int]) -> bool:
        return len(k) == 0


class E:
    def __init__(self) -> None:
        self.xs = [[1], [2, 3]]

    def __iter__(self) -> Iterator[list[int]]:
        return iter(self.xs)


print([] in C(), [1] in C(), [] not in C(), {} in D(), {"a": 1} in D())
print([2, 3] in E(), [] in E(), [] not in E(), [] in [[1], [2, 3]])
