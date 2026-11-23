# error: %d format: a real number is required, not object (narrow a value of object with isinstance() to int, float, bool, str, bytes, type or a class of the program first: it takes only str(), repr(), format(), hash(), ==, !=, is, isinstance() and a truth test otherwise)
# a %d conversion of a value of object (%s, %r and %a convert any value)
x: object = 1
print("%d" % x)
