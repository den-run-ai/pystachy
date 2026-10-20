"""Aliases of from-imported names, which other modules from-import in turn (tests/programs/imports/import_alias_reexport.py)."""
from mods.alias_base import Box, inc

plus_one = inc
Crate = Box
also = plus_one
