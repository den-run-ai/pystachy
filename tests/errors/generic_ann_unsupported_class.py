# error: class emods.badgeneric.Box is not supported: method __weird__() has a decorator
# An annotation that subscripts a generic class that cannot be declared reports why, as an
# annotation that names it does (the compiler once failed with a KeyError here).
from emods.badgeneric import Box


def f(b: Box[int]) -> int:
    return b.v


print(f(Box(1)))
