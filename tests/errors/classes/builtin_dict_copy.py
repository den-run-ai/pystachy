# error: copy.copy() of an object of Made, a class that derives from dict, is not supported yet
import copy


class Made(dict[str, int]):
    pass


m = Made(a=1)
print(copy.copy(m))
