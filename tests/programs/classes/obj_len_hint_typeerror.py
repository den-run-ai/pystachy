# Optional length hints ignore TypeError even without a user try statement.
from typing import Iterator


class Items:
    def __init__(self) -> None:
        self.items = [2, 1]

    def __iter__(self) -> Iterator[int]:
        print("iter")
        return iter(self.items)

    def __len__(self) -> int:
        print("len")
        self.items.append(3)
        raise TypeError("unknown length")


print(list(Items()))
print(sorted(Items()))
items = [0]
items.extend(Items())
print(items)
