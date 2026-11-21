# pystachy: python-int
# Comparing a JSON-shaped value to a promoting integer does not store the integer in the union.
type Document = None | bool | int | float | str | list[Document] | dict[str, Document]


def compare(value: Document, number: int | None) -> None:
    print(value == number, number == value, value != number, number != value)


def scalar(value: int | float, number: int) -> None:
    print(value == number, number == value, value != number, number != value)


wide = 2 ** 80
compare(True, 1)
compare(None, None)
compare(False, None)
compare(None, wide)
compare([1], wide)
compare({'n': 1}, wide)
compare('3', wide)
compare(2 ** 62 + 1, 2 ** 62 + 1)
compare(2.0 ** 80, wide)
compare(2.0 ** 80, wide + 1)
compare(-2.0 ** 80, -wide)
compare(float('nan'), wide)
scalar(2.0 ** 80, wide)
scalar(2.0 ** 80, wide + 1)
