# An imported module's class that the program does not use runs its body as CPython does, here
# a set display of one item type that hashes the module's object (import_set_item.py's mixed
# set, which types nothing, is rejected instead of being left out).
import mods.set_hash

print("imported")
