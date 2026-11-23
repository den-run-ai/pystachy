# Subclasses of a class template in an imported module, and one of the program's own (#962): a
# class without an __init__ of its own derives from each specialization, one with an annotated
# __init__ from the specialization its super().__init__(...) makes. Loose, whose __init__ is a
# class template, is left out: the program does not use it.
from mods.template_hierarchy import Event, Alarm, Tick
import mods.template_hierarchy as events


class Local(Event):
    def kind(self) -> str:
        return "local"


xs = [Event("a", 1), Alarm("b", 2), Local("c", 3)]
for x in xs:
    print(x.describe(), isinstance(x, Alarm), isinstance(x, events.Event))
t = Tick(5)
print(t.describe())
ys = [Event("t", 9), Tick(7)]
for y in ys:
    print(y.describe(), isinstance(y, Tick), isinstance(y, Alarm))
print(events.Alarm("z").describe())
