# == and != of a union holding complex numbers and containers: a list[int] member compares its
# items with a list[float]'s, a dict[str, int] member with a dict[str, float]'s, and a complex
# member equals no container; also in tuple search, between two such unions
def lists(x: complex | list[int], y: list[float]) -> None:
    print(x == y, y == x, x != y, y != x)


def dicts(x: complex | dict[str, int], y: dict[str, float]) -> None:
    print(x == y, y == x, x != y)


def search(x: complex | list[int], y: complex | list[int]) -> None:
    print(x == y, x in (y,), (y,).count(x), (y, x).index(x), y in (2j, x))


lists([1], [1.0])
lists([2], [1.0])
lists(1j, [1.0])
dicts({"a": 1}, {"a": 1.0})
dicts(1 + 0j, {"a": 1.0})
search(1j, 1j)
search([1], [1])
search([1], 2j)
search(2j, [1])
