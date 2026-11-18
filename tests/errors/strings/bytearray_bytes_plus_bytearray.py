# error: can't concat bytearray to bytes
# (CPython takes a bytearray where bytes's operator takes a bytes-like object, and int * bytearray
# by bytearray.__rmul__; lib's class has no reflected methods, and bytes's operators take bytes)
b = bytearray(b"b")
print(b"a" + b)
