# An optional from-import fails where its module has not bound the name when it runs: a module
# still being imported (a circular import) has bound only what its code has run so far, and a
# module binds nothing in the code CPython never runs (a Windows branch, TYPE_CHECKING, an
# imported module's __main__ block), whether it is imported by then or not.
import loader.part.cyc_a

print(loader.part.cyc_a.cyc_b.g(), loader.part.cyc_a.v, loader.part.cyc_a.w)
try:
    from loader.part.dropped import val
except ImportError:
    val = -1
try:
    from loader.part.dropped import tc
except ImportError:
    tc = -2
import loader.part.dropped

try:
    from loader.part.dropped import mn
except ImportError:
    mn = -3
try:
    from loader.part.dropped import here
except ImportError:
    here = -4
print(val, tc, mn, here)
