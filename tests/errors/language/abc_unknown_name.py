# error: abc_unknown_name.py:2: error: cannot import name 'Sortable' from 'collections.abc'
from collections.abc import Mapping, Sortable

d: Mapping[str, int] = {}
