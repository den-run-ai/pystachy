# functools.cached_property: the method runs once for an object, which keeps what it returned;
# of several types, read through the three ways a module names the decorator, beside a
# property, and in a subclass.
import functools
import functools as ft
from functools import cached_property
from typing import Optional


class Report:
    def __init__(self, rows: list[int], title: Optional[str] = None) -> None:
        self.rows = rows
        self.title = title
        self.log: list[str] = []

    @cached_property
    def total(self) -> int:
        self.log.append("total")
        return sum(self.rows)

    @functools.cached_property
    def squares(self) -> list[int]:
        self.log.append("squares")
        return [r * r for r in self.rows]

    @ft.cached_property
    def heading(self) -> Optional[str]:
        self.log.append("heading")
        return self.title.upper() if self.title is not None else None

    @cached_property
    def summary(self) -> "dict[str, int]":
        self.log.append("summary")
        return {"total": self.total, "count": len(self.rows)}

    @property
    def plain(self) -> int:
        self.log.append("plain")
        return len(self.rows)


class Detailed(Report):
    @cached_property
    def widest(self) -> int:
        self.log.append("widest")
        return max(self.rows)


r = Report([1, 2, 3], "t")
print(r.total, r.total, r.squares, r.squares is r.squares, r.heading, r.heading, r.summary, r.summary, r.plain, r.plain)
print(r.log)
r.rows.append(10)
print(r.total, r.squares, r.plain, Report([5]).total, Report([]).heading, Report([]).heading)
d = Detailed([4, 9, 2])
print(d.widest, d.widest, d.total, d.total, d.log)
