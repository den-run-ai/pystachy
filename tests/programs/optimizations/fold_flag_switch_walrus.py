# if NAME: right after NAME = True is not decided where the branch that runs binds a name of the
# other branch only through := in a value, which folding may drop too ((x := 1) if False else 0):
# both branches are compiled, and reading x raises NameError, as in CPython.
FLAG = True
if FLAG:
    y = (x := 1) if False else 0
else:
    x = 2
try:
    print(x)
except NameError:
    print("caught", y)
