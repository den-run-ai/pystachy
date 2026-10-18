# error: lib_collections_namedtuple_field_defaults.py:5: error: Positions._field_defaults is not supported where its defaults are all None (a dict of None values)
# (dis.py's Positions, whose defaults are [None] * 4)
from collections import namedtuple
Positions = namedtuple("Positions", ["lineno", "end_lineno"], defaults=[None] * 2)
print(Positions._field_defaults)
