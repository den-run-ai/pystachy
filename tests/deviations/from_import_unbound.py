# Documented deviation: from m import x of a global that m's code has not bound (here because
# of a circular import) raises AttributeError, where CPython raises ImportError naming m's file:
# cannot import name 'x' from partially initialized module 'circ.first' (most likely due to a
# circular import) (/path/to/circ/first.py)
from circ import first

print(first.f())
