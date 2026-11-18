from enum import StrEnum


class Word(StrEnum):
    A = "a"

    def __eq__(self, other) -> bool:
        print("word eq")
        return NotImplemented

    def __ne__(self, other) -> bool:
        print("word ne")
        return NotImplemented

    def __lt__(self, other) -> bool:
        print("word lt")
        return NotImplemented

    def __gt__(self, other) -> bool:
        print("word gt")
        return NotImplemented


def compare(value) -> None:
    member = Word.A
    print("value", value)
    print(member == value, value == member, member != value, value != member)
    print(member in (value,), value in (member,))
    try:
        print(member < value, value > member)
    except TypeError:
        print("ordering error")


compare("a")
compare("b")


def optional(value: str | None) -> None:
    compare(value)


optional("a")
optional(None)
Word.A._value_ = "z"
compare("a")
compare("z")
print(hasattr(Word.A, " enum str"))


class EqOnly(StrEnum):
    A = "a"

    def __eq__(self, other) -> bool:
        print("eq only")
        return NotImplemented


print(EqOnly.A == "a", "a" == EqOnly.A, EqOnly.A != "a", "a" != EqOnly.A)
print(EqOnly.A == "z", "z" == EqOnly.A, EqOnly.A != "z", "z" != EqOnly.A)
EqOnly.A._value_ = "z"
print(EqOnly.A == "a", "a" == EqOnly.A, EqOnly.A != "a", "a" != EqOnly.A)
