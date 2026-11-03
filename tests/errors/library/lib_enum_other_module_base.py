# error: enum class Hue is not supported: it derives from Shade, an enum class of another module
# The compiler makes an enum class from a class statement whose base it finds in its own module (CPython prints <Hue.TEAL: 1>)
from enum_palette import Shade


class Hue(Shade):
    TEAL = 1


print(repr(Hue.TEAL))
