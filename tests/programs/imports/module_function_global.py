# A module global that only a function of its module assigns (global x; x = ...), read by
# other modules as m.x or by the module's own code: the function is compiled first, and its
# assignment gives the global its type. Reads that may come before it raise as in CPython.
import infer.conf as conf
from infer.conf import setup, get


def show() -> None:
    print(conf.late + 1)


conf.setup()
print(conf.late)
show()
setup()
print(get())
conf.setup_names()
print(conf.names, len(conf.names))


def getg() -> int:
    return g


def setg() -> None:
    global g
    g = 5


setg()
print(getg(), g)
