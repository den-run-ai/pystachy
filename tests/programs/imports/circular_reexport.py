# A module's copy of another module's constant (from m import K, as mypy's types.py re-exports
# type_visitor's ANY_STRATEGY), and a copy of that copy, can be read by a module that this module
# imports and that imports it back, as the constant itself can: the import that binds the copy has
# run by then. Final, int, str, bool and float constants.
import reexpkg.types_

print(reexpkg.types_.run())
