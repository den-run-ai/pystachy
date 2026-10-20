"""Binds an alias, then imports a module that imports it back (tests/programs/imports/import_alias_reexport.py)."""
from mods.alias_base import inc

first = inc
import mods.alias_cyc_b
