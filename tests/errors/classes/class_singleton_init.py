# error: class_singleton_init.py:7: error: 'Registry' is bound both as a variable and as a function, class or import (not supported)
# a class rebound to its instance whose call runs its __init__, which might read the name where
# CPython's is still the class, is not supported (class_singleton)
class Registry:
    def __init__(self) -> None:
        self.items: list[int] = []
Registry = Registry()
print(Registry.items)
