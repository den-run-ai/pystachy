# error: copy.deepcopy() of a value of type Generator[int] is not supported
# CPython raises TypeError: cannot pickle 'generator' object
import copy


def gen():
    yield 1


print(list(copy.deepcopy(gen())))
