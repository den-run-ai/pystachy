# error: cannot compare list[A] == list[B] (making the table of list[B] as object (for list[A] == its object)
# == of two values of object compiles the comparison of each pair of the types stored as object,
# where a list of one class and a list of another are not compared yet
class A:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, A)


class B:
    pass


def main() -> None:
    x: object = [A()]
    y: object = [B()]
    print(x == y)


main()
