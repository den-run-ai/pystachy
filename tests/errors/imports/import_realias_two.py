# error: 'one' is bound by two imports, to different modules, functions or classes (not supported)
from emods.realias import plus_one as one
from emods.realias import minus_one as one

print(one(1))
