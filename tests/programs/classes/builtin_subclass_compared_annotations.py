from typing import Optional as Maybe


class Stack(list[int]):
    pass


class Table(dict[str, int]):
    pass


def keep_list(value: list[int]) -> list[int]:
    return value


def keep_dict(value: dict[str, int]) -> dict[str, int]:
    return value


class Named:
    def __eq__(self, other):
        print(type(other).__name__)
        return isinstance(other, (Stack, Table))


class Lists:
    def __eq__(self, other: list[int] | None) -> bool:
        if other is None:
            return False
        held = keep_list(other)
        print(type(held).__name__, held is other)
        return isinstance(held, Stack) and len(held) == 1

    def __lt__(self, other: "list[int] | None") -> bool:
        return other is not None and isinstance(other, Stack)


class Dicts:
    def __eq__(self, other: Maybe[dict[str, int]]) -> bool:
        if other is None:
            return False
        held = keep_dict(other)
        print(type(held).__name__, held is other)
        return isinstance(held, Table) and held["a"] == 2


def main() -> None:
    s = Stack()
    s.append(1)
    d = Table()
    d["a"] = 2
    print(Named() == s, s == Named(), Named() == d, d == Named())
    print(Lists() == s, s == Lists(), Lists() != s, s != Lists())
    print(Lists() < s, s > Lists())
    print(Dicts() == d, d == Dicts())
    print(s in (Lists(),), Lists() in (s,))
    print(d in (Dicts(),), Dicts() in (d,))


main()
