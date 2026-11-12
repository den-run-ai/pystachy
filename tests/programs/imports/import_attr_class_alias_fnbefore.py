# A name bound to another module's class that a function defined before the statement reads is a
# variable holding the class object (#7): a call before the statement finds the name unbound and
# raises CPython's NameError
import mods.attralias_shapes as shapes


def make() -> None:
    print(type(B(1)).__name__)


try:
    make()
except NameError as e:
    print("NameError:", e)
B = shapes.Box
make()
