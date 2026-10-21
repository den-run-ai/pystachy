from typing import Iterable


def note() -> dict[str, int]:
    print("dict unpacking effect")
    return {"value": 1}


class Table:
    data = {**note()}
    xs: Iterable[int]
