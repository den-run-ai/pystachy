# pystachy: python-int
# Documented deviation of the python-int prototype (docs/python-int.md): CPython
# shares one constant object between these equal literals and prints True. Equal
# prototype values outside CPython's small-int cache are distinct wrappers whose
# CPython identity depends on how CPython made each object, so it raises.
a = 1000
b = 1000
try:
    print(a is b)
except NotImplementedError as e:
    print("NotImplementedError:", e)
