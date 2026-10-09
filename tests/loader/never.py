# A module with a syntax error, imported only where CPython never runs the import
# (tests/fold_idioms.py): it must not be loaded at all.
def f(:
    pass
