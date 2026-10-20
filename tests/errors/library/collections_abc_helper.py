# error: collections_abc_helper.py:4: error: collections.abc._check_methods is not supported: Pystachy's collections.abc (which _collections_abc is too) has only the ABCs
# CPython's collections.abc, the module _collections_abc, also binds helpers, the types of iterators
# and views, and its imports: Pystachy lacks them
from _collections_abc import Mapping, _check_methods
