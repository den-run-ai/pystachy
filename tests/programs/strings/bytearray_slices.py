b = bytearray(b"abcdefgh")
print(b[1:3], b[:2], b[5:], b[::2], b[::-1], b[-3:-1], b[10:], b[3:1], b[6:1:-2])
b[1:3] = b"XYZ"
print(b)
b[0:0] = bytearray(b"__")
print(b)
b[::3] = b"1234"
print(b)
del b[2:5]
print(b)
del b[::2]
print(b)
b[1:2] += b"!!"
print(b)
b[:] = [72, 105]
print(b, len(b))
c = b
b[len(b):] = b
print(b, c is b)
try:
    b[::2] = b"toolong"
except ValueError as e:
    print("ValueError:", e)
try:
    b[0:1:0] = b"x"
except ValueError as e:
    print("ValueError:", e)
