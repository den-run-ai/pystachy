# Documented deviation: reading an attribute of a module whose code is still running (here
# because of a circular import) before that code binds it raises AttributeError naming only the
# module, where CPython also says it is partially initialized and names its file:
# partially initialized module 'circ.third' from '/path/to/circ/third.py' has no attribute 'y'
# (most likely due to a circular import)
from circ import third

print(third.y)
