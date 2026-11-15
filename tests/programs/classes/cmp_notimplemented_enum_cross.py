from enum import IntEnum


class Declining(IntEnum):
    ONE = 1

    def __eq__(self, other) -> bool:
        print("decl eq")
        return NotImplemented

    def __ne__(self, other) -> bool:
        print("decl ne")
        return NotImplemented

    def __lt__(self, other) -> bool:
        print("decl lt")
        return NotImplemented

    def __le__(self, other) -> bool:
        print("decl le")
        return NotImplemented

    def __gt__(self, other) -> bool:
        print("decl gt")
        return NotImplemented

    def __ge__(self, other) -> bool:
        print("decl ge")
        return NotImplemented


class Plain(IntEnum):
    ONE = 1
    TWO = 2


def compare(a: Declining, b: Plain) -> None:
    print("pair", b.value)
    print("==", a == b, b == a)
    print("!=", a != b, b != a)
    print("<", a < b, b < a)
    print("<=", a <= b, b <= a)
    print(">", a > b, b > a)
    print(">=", a >= b, b >= a)


compare(Declining.ONE, Plain.ONE)
compare(Declining.ONE, Plain.TWO)
