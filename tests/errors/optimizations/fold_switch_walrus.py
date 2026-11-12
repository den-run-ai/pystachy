# error: fold_switch_walrus.py:6: error: name 'Missing' is not defined
# The names that := binds in the branch that does not run count as its names too (Extra): this
# test is not decided, and both branches are compiled.
MYPYC = False
if MYPYC:
    Kind = (Extra := Missing)
else:
    Kind = "native"
print(Kind)
