"""Binds a TypeVar only after importing a module that imports it back (tests/errors/generics/typevar_import_cycle.py)."""
from typing import TypeVar

from emods.tv_cyc_b import ident

T = TypeVar("T")
