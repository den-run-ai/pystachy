# error: needs_c.py:6: error: module '_pystachy_absent_c' is not supported: it is not a builtin module
# An import that is not optional of a module that imports one whose import of a missing module
# fails is that import's error too.
import absentmods.through
