# error: 'is' is only supported for objects and None
# The views' in tests identity and then equality, as CPython's v is value or v == value: 'is'
# between a number and a str is not supported, where CPython's is false
from collections.abc import Mapping


class Prices(Mapping):
    def __init__(self) -> None:
        self.d = {"tea": 3, "jam": 5}

    def __getitem__(self, k: str) -> int:
        return self.d[k]

    def __iter__(self):
        return iter(self.d)

    def __len__(self) -> int:
        return len(self.d)


print("5" in Prices().values())
