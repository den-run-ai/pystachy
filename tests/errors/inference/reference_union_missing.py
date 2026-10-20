# error: must declare method read()
class A:
    def read(self) -> str:
        return "a"


class B:
    pass


def check(value: A | B) -> None:
    print(value.read())


check(A())
