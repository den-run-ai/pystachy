# A from-import of a submodule that is not found, of a package that is.
print("frompkg: before the import")
from absentmods.nothere import thing
print("frompkg: not reached", thing)
