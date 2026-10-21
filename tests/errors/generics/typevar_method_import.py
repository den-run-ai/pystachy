# error: method '__init__' of class 'Holder' mentions TypeVar '_D', which is not supported: __init__() is not a template
from emods.generic import Box, Holder, default

print(default(1), Box(1).v, Box(1).get("x"))
print(Holder(1).v)
