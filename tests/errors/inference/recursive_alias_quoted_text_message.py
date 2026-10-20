# error: recursive_alias_quoted_text_message.py:16: error: 'C' object has no attribute 'rec[1]'
# Messages name a recursive alias's internal edge type as the alias, but quote the program's own
# text as written, even text that looks like such a type.
type V = int | list[V]


class C:
    def __init__(self) -> None:
        self.x = 1


def main(values: list[V]) -> None:
    c = C()
    for value in values:
        print(value)
    print(getattr(c, "rec[1]"))


main([1, [2]])
