# error: 're' is read in escaped() where Pystachy cannot tell that the import in it that binds 're' has run
# A generator expression reads the names around it where it runs, which may be after the import
# has run, and checks no binding flag there (CPython: NameError, cannot access free variable, where
# the import has not run).
def escaped(flag: bool) -> list[str]:
    if flag:
        import re
    return list(re.escape(s) for s in ["a.b"])


print(escaped(True))
