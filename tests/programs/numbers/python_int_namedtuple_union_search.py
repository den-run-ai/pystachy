# A tuple search splits class unions before comparing a nullable NamedTuple's wide fields.
# Keep the union's lenient comparison for a template method that cannot take the other
# operand, even when the NamedTuple's None and non-None paths are compiled separately.
# pystachy: python-int
from typing import NamedTuple


class NT(NamedTuple):
    value: int


class Other:
    def __eq__(self, other) -> bool:
        return other.missing()


def search(needle: NT, item: NT | Other) -> None:
    print(needle in (item,), item in (needle,))
    print((item, needle).count(needle), (needle, item).count(item))
    print((needle, item).index(item), (item, needle).index(needle))


for value in [1, 2 ** 70, -(2 ** 70)]:
    search(NT(value), NT(value))
    search(NT(value), NT(value + 1))
    search(NT(value), None)
    search(None, NT(value))
search(None, None)
