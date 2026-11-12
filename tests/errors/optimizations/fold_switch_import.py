# error: fold_switch_import.py:6: error: module 'sqlite3' is not supported
# if NAME: right after NAME = False is decided only where the branch that does not run only
# assigns names: an import (here of a module that Pystachy lacks) keeps both branches compiled.
MYPYC = False
if MYPYC:
    import sqlite3 as Kind
else:
    Kind = "native"
print(Kind)
