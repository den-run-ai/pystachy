# An optional from-import of a name its module binds in a with block, which always runs its body,
# takes the name (it is not a name bound only in a branch).
try:
    from loader.optd.in_with import x
except ImportError:
    x = -1
print(x)
