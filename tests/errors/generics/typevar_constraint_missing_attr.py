# error: typevar_constraint_missing_attr.py:7: error: module 'mods.shapes' has no attribute 'Missing' (CPython evaluates a TypeVar's constraints and bound when the assignment runs)
# CPython evaluates a TypeVar's constraints when the assignment runs, also inside a subscript:
# an attribute that its module does not bind raises AttributeError.
from typing import TypeVar
import mods.shapes

T = TypeVar("T", mods.shapes.Square, list[mods.shapes.Missing])
print("never")
