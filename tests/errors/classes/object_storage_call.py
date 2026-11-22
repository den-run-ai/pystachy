# error: 'object' object is not callable (narrow a value of object with isinstance() to int, float, bool, str, bytes, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)
# a call of a value of object (its object may be a class, or an object whose class has __call__)
class C:
    pass


x: object = C
print(x())
