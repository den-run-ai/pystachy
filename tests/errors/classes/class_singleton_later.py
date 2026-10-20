# error: class_singleton_later.py:7: error: 'Mode' is bound both as a variable and as a function, class or import (not supported)
# a class rebound to its instance by an assignment that does not directly follow the class
# statement is not supported (class_singleton)
class Mode:
    pass
print("between")
Mode = Mode()
