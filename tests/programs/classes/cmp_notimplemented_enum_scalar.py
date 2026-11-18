from enum import IntEnum


class Number(IntEnum):
    ONE = 1

    def __eq__(self, other) -> bool:
        print("enum eq")
        return NotImplemented

    def __ne__(self, other) -> bool:
        print("enum ne")
        return NotImplemented

    def __lt__(self, other) -> bool:
        print("enum lt")
        return NotImplemented

    def __gt__(self, other) -> bool:
        print("enum gt")
        return NotImplemented


def compare(value) -> None:
    member = Number.ONE
    print("value", value)
    print(member == value, value == member, member != value, value != member)
    print(member in (value,), value in (member,))
    try:
        print(member < value, value > member)
    except TypeError:
        print("ordering error")


compare(1)
compare(2)
compare(1.0)
compare(2.0)
compare(True)
compare(False)
compare(float("nan"))
compare(Number.ONE)


def optional(value: int | None) -> None:
    compare(value)


optional(1)
optional(None)
Number.ONE._value_ = 99
compare(1)


class EqOnly(IntEnum):
    ONE = 1

    def __eq__(self, other) -> bool:
        print("eq only")
        return NotImplemented


member = EqOnly.ONE
print(member == 1, 1 == member, member != 1, 1 != member)
print(member == 1.0, 1.0 == member, member != 1.0, 1.0 != member)


class Answer(IntEnum):
    ONE = 1

    def __eq__(self, other) -> bool:
        print("answer eq")
        return False

    def __ne__(self, other) -> bool:
        print("answer ne")
        return True


print(Answer.ONE == 1, 1 == Answer.ONE, Answer.ONE != 1, 1 != Answer.ONE)
print(Answer.ONE == 1.0, 1.0 == Answer.ONE, True == Answer.ONE, True != Answer.ONE)
