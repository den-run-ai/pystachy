# A module-level name bound to one class and then to a class deriving from it is a variable
# holding the class object (#7): the call makes an object of the class it holds then
import mods.attralias_shapes

B = mods.attralias_shapes.Box
B = mods.attralias_shapes.Crate
print(B(1).v)
