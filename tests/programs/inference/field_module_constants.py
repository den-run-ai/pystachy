# A field stored from a module global that one assignment binds (x = v, x: Final = v, or a
# from-import of such a name, also read as module.x) takes the type of that value, typed in its
# own module: a comparison, an int that another global's value computes, a str, a float, an
# object and a list
from fconsts.defs import HAVE_IMMORTAL, HEIGHT, NAME, NAMES, RATIO, STRINGS, WIDTH
import fconsts.defs

LOCAL = 3


class Shape:
    def __init__(self, scale: int) -> None:
        self.immortal = HAVE_IMMORTAL
        self.width = WIDTH
        self.height = HEIGHT
        self.name = NAME
        self.ratio = RATIO
        self.dep = STRINGS
        self.names = NAMES
        self.local = LOCAL
        self.qualified = fconsts.defs.WIDTH
        self.scaled = WIDTH * scale


s = Shape(3)
print(s.immortal, s.width, s.height, s.name)
print(s.ratio, s.dep, s.names, s.local, s.qualified, s.scaled)
s.width = 10
s.names.append("c")
print(s.width, NAMES)
