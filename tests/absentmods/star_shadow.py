# A module whose star import may bind the name ModuleNotFoundError before its import of a
# missing module.
from absentmods.shadow_names import *

print("star_shadow: before the import")
import _pystachy_absent_c
print("star_shadow: not reached")
