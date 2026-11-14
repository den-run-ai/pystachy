# A cached_property's attribute assigned and deleted: an assignment replaces what the object
# keeps without a call, and del forgets it, so that the next read calls the method again.
from functools import cached_property


class Report:
    def __init__(self, rows: list[int]) -> None:
        self.rows = rows
        self.computed = 0

    @cached_property
    def total(self) -> int:
        self.computed += 1
        return sum(self.rows)

    @cached_property
    def label(self) -> str:
        self.computed += 1
        return f"{len(self.rows)} rows"


r = Report([1, 2, 3])
print(r.total, r.total, r.label, r.label, r.computed)
r.rows.append(4)
print(r.total, r.computed)
del r.total
print(r.total, r.computed)
r.total = 100
print(r.total, r.computed)
del r.total
print(r.total, r.computed)
try:
    del r.total
    del r.total
except AttributeError as e:
    print("AttributeError", e)
q = Report([5])
q.total = 7
print(q.total, q.computed, q.label, q.computed)
