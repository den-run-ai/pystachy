# Definition time: an imported module's def and class statements run when it is imported. The
# default values Pystachy compiles run then (in order with the module's other code), and the
# decorators, default values, bases and class bodies it leaves uncompiled, in functions and
# classes the program never uses, are the ones that do nothing then. class C(object) is a
# plain class.
print("main: start")
import defmods.unused as u
from defmods.unused import Plain


class Local(object):
    def __init__(self, name: str):
        self.name = name


print(u.LIMIT, u.counted(), Plain(21).twice(), Local("x").name)
