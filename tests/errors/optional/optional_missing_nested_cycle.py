# error: cyc_b.py:4: error: module '_pystachy_absent_c' is not supported: it is not a builtin module
# Two modules that import each other, the second of which imports a missing module: its import
# of the first, whose code is running, succeeds as in CPython, and the missing import is the
# error of an import that is not optional.
import absentmods.cyc_a
