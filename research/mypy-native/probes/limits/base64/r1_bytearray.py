b = bytearray()
b += b"abcdefgh"
b[-3:] = b"==="
print(bytes(b), len(b))
