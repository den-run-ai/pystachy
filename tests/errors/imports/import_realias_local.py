# error: 'one' is bound both as a variable and by an import (not supported)
def first() -> int:
    from emods.realias import plus_one as one
    one = 5
    return one


print(first())
