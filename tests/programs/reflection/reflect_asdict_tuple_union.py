# asdict()'s values of different types join in a union, which holds one tuple type
from dataclasses import asdict, dataclass


@dataclass
class Item:
    name: str
    pair: tuple[int, int]
    ok: bool


def main() -> None:
    d = asdict(Item("a", (1, 2), True))
    print(d)
    p = d["pair"]
    if isinstance(p, tuple):
        print(p[0] + p[1], len(p))
    print(d["pair"] == (1, 2), d["name"] == "a", d["ok"] == (1, 2), len(d))


main()
