# error: 'is' between ints is not supported in python-int modules yet
# pystachy: python-int
x = 2 ** 70
y = x + 0
print(x is y)
