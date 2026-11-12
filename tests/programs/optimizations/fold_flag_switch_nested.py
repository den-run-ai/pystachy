# if NAME: right after NAME = True is not decided where the branch that runs binds a name of the
# other branch only in a nested block, which may be dropped too (if False: x = 1): both branches
# are compiled, and reading x raises NameError, as in CPython.
FLAG = True
if FLAG:
    if False:
        x = 1
else:
    x = 2
try:
    print(x)
except NameError:
    print("caught")
