# error: cannot tell whether module 'emods.del_in_branch' has bound 'x' when this optional import runs
# The module deletes x in a branch, which runs here: CPython runs the except clause, where an
# AttributeError at run time would be wrong; Pystachy cannot tell whether the branch runs.
try:
    from emods.del_in_branch import x
except ImportError:
    x = -1
print(x)
