# == of two values of object compiles the comparison of each pair of the types stored as object:
# a list of one class and a list of another, item by item, the first's __eq__ asked of the other
class A:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, A)


class B:
    pass


def main() -> None:
    x: object = [A()]
    y: object = [B()]
    z: object = [A()]
    print(x == y, x == z, y == y, x != y)


main()
