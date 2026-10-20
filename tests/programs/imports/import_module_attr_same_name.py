# A function's import of a module with an attribute of the module's own name: fnmatch.fnmatch
# (a def) and bisect.bisect (bisect_right by another name) are the modules' functions, not the
# modules (the loader once rejected these: name 'fnmatch' is not defined).
def matches(name: str) -> bool:
    import fnmatch
    return fnmatch.fnmatch(name, "*.py")


def position(xs: list[int], x: int) -> int:
    import bisect
    return bisect.bisect(xs, x)


print(matches("a.py"), matches("b.txt"))
print(position([1, 3, 5], 4))
