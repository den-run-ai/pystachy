# error: class 'mods.attralias_shapes.Box' cannot be used as a value
import mods.attralias_shapes

B = mods.attralias_shapes.Box


def rebind() -> None:
    global B
    B = mods.attralias_shapes.Crate


print(B(1).v)
