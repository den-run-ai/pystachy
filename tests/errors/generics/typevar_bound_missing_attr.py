# error: typevar_bound_missing_attr.py:7: error: module 'mods.shapes' has no attribute 'Missing' (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# CPython evaluates a TypeVar's bound when the assignment runs: an attribute that its module
# does not bind raises AttributeError, as it does in a def's annotation.
from typing import TypeVar
import mods.shapes

T = TypeVar("T", bound=mods.shapes.Missing)
print("never")
