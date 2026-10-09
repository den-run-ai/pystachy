# Imports cyc_b before it binds f and v: cyc_b's optional from-imports of them find this module
# partially initialized, and run their except clauses (tests/optional_partial.py).
from loader.part import cyc_b


def f() -> str:
    return "fast"


v = 1
w = cyc_b.w
