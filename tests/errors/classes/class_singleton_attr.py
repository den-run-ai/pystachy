# error: class_singleton_attr.py:6: error: 'Sentinel' object has no attribute 'missing'
# (CPython's AttributeError names the class of a class rebound to its instance: class_singleton)
class Sentinel:
    pass
Sentinel = Sentinel()
print(Sentinel.missing)
