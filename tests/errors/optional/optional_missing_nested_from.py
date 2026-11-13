# error: needs_c.py:6: error: module '_pystachy_absent_c' is not supported: it is not a builtin module
# A from-import that is not optional of a submodule whose import of a missing module fails is
# that import's error too, also after an optional import of the submodule took its handler.
try:
    import absentmods.needs_c
except ImportError:
    print("fallback")
from absentmods import needs_c

print(needs_c.version())
