# The fallback to class boxes is a module's: a module that opts in to dynamic Any, names no
# type[C] and does not compile with typed class objects keeps its class boxes when a module that
# does name type[C] imports it, and that module's class objects stay typed (#7).
# pystachy: dynamic-any
from typing import Any
import dynany_classbox_support.registry as registry
from dynany_classbox_support.registry import Loud, Plugin


def make(kind: type[Plugin], name: str) -> Plugin:
    return kind(name)


chosen: type[Plugin] = Loud
print(registry.names(), registry.holds(Loud), registry.holds(int), registry.holds(chosen))
print(type(make(chosen, "x")).__name__, make(Plugin, "y").name, chosen is Loud)
held: Any = chosen
print(registry.holds(held), held is Loud)
