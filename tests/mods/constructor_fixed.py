from collections.abc import Iterable


class Count:
    def __init__(self, values: Iterable[int]) -> None:
        self.value: int = sum(values)

    def read(self) -> int:
        return self.value


class Unused:
    def __init__(self, values: Iterable[int]) -> None:
        self.value: int = values.unsupported()

    def __str__(self) -> str:
        return self.value.unsupported()
