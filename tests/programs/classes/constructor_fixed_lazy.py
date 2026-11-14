from typing import Iterable


class Unused:
    def __init__(self, values: Iterable[int]) -> None:
        self.value: int = values.no_such_method()

    def __str__(self) -> str:
        return self.value.no_such_method()


class DeferredAnnotation:
    def __init__(self, source):
        self.value: "UnsupportedType" = source


class Used:
    def __init__(self, values: Iterable[int]) -> None:
        self.value: int = sum(values)

    def __str__(self) -> str:
        return str(self.value)


print(Used([1, 2]), Used((3, 4)))
print("unused constructors and methods stay lazy")
