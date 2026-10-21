# error: class 'mods.attralias_shapes.Box' cannot be used as a value
# (an alias through a module's attribute that a function defined before it reads stays an error: a
# call before the alias's statement would find the name unbound, where CPython raises NameError)
import mods.attralias_shapes as shapes


def make() -> None:
    print(type(B(1)).__name__)


try:
    make()
except NameError as e:
    print("NameError:", e)
B = shapes.Box
make()
