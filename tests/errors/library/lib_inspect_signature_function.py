# error: cannot import name 'signature' from 'inspect'
# inspect.signature() reads a function's code object, which a compiled program does not have:
# the module does not define it, and a name it lacks is no stub
from inspect import signature


def area(width: int, height: int = 1) -> int:
    return width * height


print(signature(area))
