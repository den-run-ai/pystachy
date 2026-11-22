# error: static_dynamic_any.py:1: error: '# pystachy: static' and '# pystachy: dynamic-any' cannot both apply to a module
# pystachy: static
# pystachy: dynamic-any
# The two markers contradict each other: one makes typing.Any a dynamic value in the module, and
# the other rejects every Any value there.
print(1)
