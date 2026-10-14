# error: 'int' object is not callable
# CPython accepts a noncallable callback when it will never be invoked, but
# compiling reduce checks its callback type for every input length.
from functools import reduce

print(reduce(42, '1'))
