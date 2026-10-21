# An isinstance() test that the static types decide still looks its class up: before the class
# statement has run, it raises NameError (uncaught here: the program exits with status 1)
class A:
    pass


a = A()
print("before")
if isinstance(a, B):
    print("B")
print("not reached")


class B:
    pass
