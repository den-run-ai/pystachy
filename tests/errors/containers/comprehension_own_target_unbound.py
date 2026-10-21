# error: comprehension_own_target_unbound.py:6: error: 'x' is read before the comprehension's for clause that binds it, where CPython raises UnboundLocalError (not supported)
# The target d[x], x assigns d[x] before x: that x is the comprehension's own, still unbound
# (not the module's x)
x = 5
d = {1: 0, 5: 0}
print([0 for d[x], x in [(1, 2)]])
