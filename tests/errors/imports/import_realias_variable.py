# error: 'one' is bound both as a variable and by an import (not supported)
from emods.realias import count as one
from emods.realias import plus_one as one

print(one(1))
