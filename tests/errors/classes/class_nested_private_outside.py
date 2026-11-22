# error: class_nested_private_outside.py:10: error: type object 'Outer' has no attribute '__Hidden'
# A class nested under a private name is Outer._Outer__Hidden outside the class, which mangles
# nothing there: CPython's Outer.__Hidden raises AttributeError.
class Outer:
    class __Hidden:
        x = 1


print(Outer._Outer__Hidden.x)
print(Outer.__Hidden.x)
