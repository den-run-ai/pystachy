# error: collections_abc_unknown_name.py:3: error: cannot import name 'Sortable' from 'collections.abc'
# (CPython's message too: _collections_abc's __name__ is "collections.abc")
from _collections_abc import Sequence, Sortable

xs: Sequence[int] = [1]
