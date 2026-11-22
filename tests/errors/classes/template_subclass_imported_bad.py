# error: class mods.template_hierarchy.Loose is not supported: a subclass of class template mods.template_hierarchy.Event whose own __init__ is a class template is not supported
# An imported module's subclass of a class template is compiled where the program uses it, with
# the rules of a subclass of the program's own: one whose __init__ is a class template is not.
from mods.template_hierarchy import Event, Loose

print(Event("e").describe())
print(Loose(1).describe())
