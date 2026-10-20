# A module whose dataclasses or property setters Pystachy cannot compile, but the program does
# not use: its other classes work, also those deriving from the same base.
from mods import points
from mods.points import Labeled, Point

ps: list[Point] = [Point(1), Labeled(-2), points.Point(3, "q")]
for p in ps:
    print(p, p.norm(), p == Point(1), p.origin())
print(Labeled(5) == Labeled(5), points.Labeled(1, "n", "ł"))
