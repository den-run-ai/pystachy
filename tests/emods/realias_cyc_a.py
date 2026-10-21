"""Binds an alias only after importing a module that imports it back (tests/errors/imports/import_realias_cycle.py)."""
from emods.realias_base import inc
import emods.realias_cyc_b

later = inc
