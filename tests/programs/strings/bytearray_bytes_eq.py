# bytes == bytearray, and other operands on the left: bytearray's reflected __eq__ and __ne__ decide,
# as in CPython (its methods give way to another operand's with NotImplemented).
b = bytearray(b"ab")
print(b"ab" == b, b"ab" != b, b"x" == b, b"x" != b, b == b"ab", "ab" == b, 3 == b, None == b)
xs = [b"ab", b"zz"]
print(b in [bytearray(b"zz"), bytearray(b"ab")], xs.count(b"ab"))
