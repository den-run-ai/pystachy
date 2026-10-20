"""Binds a type alias only after importing a module that imports it back (tests/errors/reflection/type_alias_import_cycle.py)."""
from emods.ta_cyc_b import width

Row = list[int]
