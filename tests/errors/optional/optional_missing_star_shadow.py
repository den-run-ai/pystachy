# error: star_shadow.py:6: error: module '_pystachy_absent_c' is not supported: it is not a builtin module
# A module whose star import may bind the name ModuleNotFoundError is not taken as failing at its
# import of a missing module: that import stays an error, also for an optional import of the
# module (the compiler once emitted a reference to a guard it never defined).
try:
    import absentmods.star_shadow
except ImportError:
    print("fallback")
