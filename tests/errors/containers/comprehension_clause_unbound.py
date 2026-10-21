# error: comprehension_clause_unbound.py:6: error: 'b' is read before the comprehension's for clause that binds it, where CPython raises UnboundLocalError (not supported)
# A later clause's iterable reads the comprehension's own b, which only the clause after it binds
# (the module's b is not what it reads): CPython raises UnboundLocalError once the outer
# iterable has an item
b = [5]
print([a + c for a in [1] for c in b for b in [2]])
