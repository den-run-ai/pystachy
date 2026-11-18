# A module-level name bound to another module's class that a function rebinds (global B) is a
# variable holding the class object (#7), not an alias: the call makes an object of the class it
# holds then
import mods.attralias_shapes

B = mods.attralias_shapes.Box


def rebind() -> None:
    global B
    B = mods.attralias_shapes.Crate


print(B(1).v)
