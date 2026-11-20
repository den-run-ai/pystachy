# error: duplicate values found in <flag 'F'>: B -> A
# CPython's ValueError where @unique runs names a flag class <flag 'F'>
from enum import Flag, unique


@unique
class F(Flag):
    A = 1
    B = 1


print(list(F))
