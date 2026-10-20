# error: emods/subscript.py:6: error: type 'C' is not subscriptable
# An imported module's def runs, used or not, and evaluates its annotations: C[int], of a class
# that cannot be subscripted, fails the import (it was an error only where f was called).
import emods.subscript

print(emods.subscript.g())
