# An extended slice that is given no bytes loses its bytes, as CPython's bytearray does; one given
# some must be given as many as it selects.
b = bytearray(b"abcdefgh")
b[::2] = b""
c = bytearray(b"abcdefgh")
c[::-2] = bytearray()
d = bytearray(b"abcdefgh")
d[1::3] = []
e = bytearray(b"abcdefgh")
e[5:1:-1] = b""
print(b, c, d, e)
try:
    f = bytearray(b"abcdefgh")
    f[::2] = b"xy"
except ValueError as x:
    print("ValueError:", x)
