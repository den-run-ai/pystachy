a = 0
from replaced_exports import *

print(a, b, _private)

import replaced_exports

replaced_exports.__all__.append("a")
a = -1
from replaced_exports import *

print(a)
