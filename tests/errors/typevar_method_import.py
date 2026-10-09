# error: method 'get' of class 'Box' mentions TypeVar '_D', which is not supported: a method is not a template
from emods.generic import Box, default

print(default(1), Box(1).v)
print(Box(1).get(2))
