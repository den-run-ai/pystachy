# error: fold_switch_between.py:7: error: name 'Missing' is not defined
# if NAME: is decided only right after NAME = True or NAME = False: code that runs between them
# could assign NAME, so here both branches are compiled (CPython prints "between" and "native").
MYPYC = False
print("between")
if MYPYC:
    Kind = Missing
else:
    Kind = "native"
print(Kind)
