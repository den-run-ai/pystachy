# error: readonly attribute
# CPython raises AttributeError: a range object's start, stop and step cannot be assigned
r = range(3)
r.stop += 1
print(r)
