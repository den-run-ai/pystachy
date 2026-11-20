# error: Color = Enum(...) is supported with the class's name, 'Color', as its first argument
# CPython names the class Colour (repr <Colour.RED: 1>) and binds it to Color; the class statement
# the compiler makes of the call binds the class's own name
from enum import Enum

Color = Enum("Colour", "RED GREEN")
print(repr(Color.RED))
