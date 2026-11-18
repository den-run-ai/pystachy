# isinstance(x, type(y)) of values that are no objects of the program: type(y) is the class
# object of y's builtin class, which x is an instance of where its own class is that class or
# derives from it (a bool is an int).
print(isinstance(3, type(3)))
print(isinstance(True, type(3)), isinstance(3, type(True)), isinstance("s", type(3)), isinstance(None, type(None)))
