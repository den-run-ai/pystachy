# error: % formatting with a mapping is only supported where every conversion names a key (%(name)s)
d = {"a": 1}
print("%(a)s %s" % d)
