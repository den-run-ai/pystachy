# pystachy: python-int
# A recursive union still stores a signed 64-bit int. On CPython both iterations
# store the original integer at the root and in each mutable container.
type Document = int | str | list[Document] | dict[str, Document]


def root(number: int) -> Document:
    return number


def probe(number: int) -> None:
    items: list[Document] = []
    fields: dict[str, Document] = {}
    try:
        value = root(number)
        print('root', value, number in (value,), (number,).count(value))
    except OverflowError:
        print('root overflow')
    try:
        items.append(number)
    except OverflowError:
        print('list overflow')
    try:
        fields['n'] = number
    except OverflowError:
        print('dict overflow')
    print(items, fields)


probe(7)
probe(2 ** 80 + 1)
