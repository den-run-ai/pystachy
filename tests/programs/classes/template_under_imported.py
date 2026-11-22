# An imported module's class template under an ordinary class (#962): compiled where the program
# uses it, with the rules of the program's own; each specialization of Poly derives from Shape.
from mods.template_under import Shape, Poly

shapes: list[Shape] = [Shape(), Poly(3, "tri"), Poly(4, 4)]
for s in shapes:
    print(s.describe(), isinstance(s, Poly))
