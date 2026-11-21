# A class of an imported module that defines __getattr__ (#1536): CPython calls it where reading
# a field fails, here one that __init__ leaves unassigned, and for a name the class lacks.
from emods.attrhooks import Lazy, double
print(double(2))
print(Lazy(False).depth)
print(Lazy(True).depth, Lazy(True).width, getattr(Lazy(False), "depth", -1), hasattr(Lazy(False), "depth"))
