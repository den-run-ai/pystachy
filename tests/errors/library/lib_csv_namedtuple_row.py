# error: unpacking a Row into the arguments of csv.Writer._append_items() is not supported (a tuple's items are)
# lib/csv's writerow() of a NamedTuple (lib/README.md): it writes a tuple's items, which a
# NamedTuple's star does not pass
import csv
import sys
from typing import NamedTuple


class Row(NamedTuple):
    name: str
    qty: int


csv.writer(sys.stdout).writerow(Row("pen", 3))
