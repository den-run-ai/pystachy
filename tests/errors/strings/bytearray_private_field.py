# error: 'bytearray' object has no attribute '_b'
# (CPython's bytearray has no attribute of its own: lib's class keeps its buffer in a field that only
# its module reaches)
b = bytearray(b"ab")
print(b._b)
