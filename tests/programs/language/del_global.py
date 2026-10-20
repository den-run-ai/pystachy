# a function reading a global that module code deleted raises NameError
x = 1
def g() -> int:
    return x
del x
print(g())
