# error: type(x) as a value (a class object) is supported for objects of the program's classes
# the class object of a builtin type is no value outside the dynamic-Any prototype (#7)
t = type(5)
print(t)
