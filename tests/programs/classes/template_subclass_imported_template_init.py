# An imported module's subclass of a class template whose own __init__ is a class template (#962):
# compiled where the program uses it, with the rules of a subclass of the program's own. Loose(1)
# derives from the specialization that its super().__init__("loose", payload) makes, Event's for
# a str and an int, which Event("x", 2) makes too.
from mods.template_hierarchy import Event, Loose

print(Event("e").describe())
print(Loose(1).describe())
for e in [Event("x", 2), Loose(3)]:
    print(e.describe(), isinstance(e, Loose), isinstance(e, Event))
