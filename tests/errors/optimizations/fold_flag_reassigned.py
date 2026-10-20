# error: fold_flag_reassigned.py:10: error: module 'pathlib' is not supported
# TYPE_CHECKING = False that module code may bind again is no constant: its test is compiled (and
# the import it guards, of a module Pystachy lacks, is an error).
import sys

TYPE_CHECKING = False
if len(sys.argv) > 5:
    TYPE_CHECKING = True
if TYPE_CHECKING:
    import pathlib
print(TYPE_CHECKING)
