# Two modules that import each other, the second of which then imports a module that is not
# found: CPython's import of the half-run first module succeeds, and the missing import fails.
print("cyc_a: before the import")
import absentmods.cyc_b
print("cyc_a: not reached")
