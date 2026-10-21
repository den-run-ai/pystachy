# error: lib_collections_namedtuple_inherit.py:8: error: inheritance from a NamedTuple is not supported
# deriving from a namedtuple() class, as from a typing.NamedTuple one
from collections import namedtuple

Base = namedtuple("Base", "start end")


class Entry(Base):
    pass


print(Entry(1, 2))
