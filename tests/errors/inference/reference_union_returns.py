# error: reference union methods must have identical return types
class A:
    def read(self) -> int:
        return 1


class B:
    def read(self) -> str:
        return "b"


def check(value: A | B) -> None:
    print(value.read())


check(A())
