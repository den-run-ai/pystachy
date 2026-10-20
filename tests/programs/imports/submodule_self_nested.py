# A package's own "from . import util" in a block that binds util before it takes the package's
# util, as at the top level; in a loop that binds nothing else, the submodule.
import loader.nested_own

print(loader.nested_own.util)
