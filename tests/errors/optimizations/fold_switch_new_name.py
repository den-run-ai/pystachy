# error: fold_switch_new_name.py:7: error: name 'Missing' is not defined
# if NAME: right after NAME = False is not decided where the branch that does not run binds a
# name that the other branch does not (Extra): both branches are compiled.
MYPYC = False
if MYPYC:
    Extra = 1
    Kind = Missing
else:
    Kind = "native"
print(Kind)
