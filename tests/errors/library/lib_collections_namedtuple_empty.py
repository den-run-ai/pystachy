# error: lib_collections_namedtuple_empty.py:4: error: a namedtuple without fields is not supported
# (as a typing.NamedTuple without fields is not)
from collections import namedtuple
Unit = namedtuple("Unit", "")
print(Unit())
