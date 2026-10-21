# Documented deviation: an alias of a class through a module's attribute (#804), A = x.K, still
# reads x.K where its statement stands, as CPython's assignment does; here x imports y, whose
# alias runs before x's class statement, so it raises AttributeError naming only the module,
# where CPython also says it is partially initialized and names its file:
# partially initialized module 'circ.alias_x' from '/path/to/circ/alias_x.py' has no attribute
# 'K' (most likely due to a circular import)
import circ.alias_x

print("never reached")
