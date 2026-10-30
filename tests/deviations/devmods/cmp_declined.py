class Annotated:
    def __eq__(self, other: complex) -> bool:
        print("annotation body")
        return True


class Returned:
    def __eq__(self, other: int) -> int:
        print("return body")
        return 1


class Reflected:
    def __eq__(self, other: object) -> bool:
        print("reflected body")
        return True
