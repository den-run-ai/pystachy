# Tuple searches retain the existing lenient treatment of a comparison whose
# annotation cannot take the other operand, including optional scalar splits.
from enum import IntEnum, StrEnum


class Number(IntEnum):
    ONE = 1

    def __eq__(self, other: str) -> bool:
        return NotImplemented


class Word(StrEnum):
    A = "a"

    def __eq__(self, other: int) -> bool:
        return NotImplemented


print(Number.ONE in (2,), 2 in (Number.ONE,))
print(Word.A in ("b",), "b" in (Word.A,))


def numbers(value: int | None) -> None:
    print(Number.ONE in (value,), value in (Number.ONE,))


def words(value: str | None) -> None:
    print(Word.A in (value,), value in (Word.A,))


numbers(2)
numbers(None)
words("b")
words(None)
