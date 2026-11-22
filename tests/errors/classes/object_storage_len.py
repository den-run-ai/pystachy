# error: object of type 'object' has no len() (narrow a value of object with isinstance() to int, float, bool, str, bytes, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)
# len() of a value of object that isinstance() has not narrowed
x: object = "abc"
print(len(x))
