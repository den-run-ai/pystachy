# error: import eload.ownsub.sub.leaf as L: 'eload.ownsub.sub' is the package's own 'sub', not its submodule (not supported: CPython raises ImportError)
import eload.ownsub.sub.leaf as L

print(L.V)
