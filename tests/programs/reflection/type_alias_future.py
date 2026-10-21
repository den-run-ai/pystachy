# With from __future__ import annotations CPython never evaluates annotations, so they may name
# type aliases that the module's code binds further down, by an assignment or a type statement:
# in defs, a class's methods and a dataclass's fields.
from __future__ import annotations

from dataclasses import dataclass


def width(r: Row) -> Count:
    return len(r)


@dataclass
class Cell:
    at: Coord
    text: Name


class Sheet:
    def __init__(self, rows: Table) -> None:
        self.rows = rows

    def cell(self, i: Count, j: Count) -> Cell:
        return Cell((i, j), self.rows[i][j])

    def find(self, text: Name) -> Coord | None:
        for i in range(len(self.rows)):
            for j in range(len(self.rows[i])):
                if self.rows[i][j] == text:
                    return (i, j)
        return None


type Name = str
Count = int
Row = list[Name]
Table = list[Row]
type Coord = tuple[Count, Count]

sh = Sheet([["a", "b"], ["ç"]])
print(width(sh.rows[0]), sh.cell(1, 0), Count("5"))
print(sh.find("b"), sh.find("z"))
