# error: fold_flag_star.py:7: error: module 'sqlite3' is not supported
# A star import may bind TYPE_CHECKING again (eload/tcstar.py binds it to True), so the test is
# compiled.
TYPE_CHECKING = False
from eload.tcstar import *
if TYPE_CHECKING:
    import sqlite3
print(TYPE_CHECKING)
