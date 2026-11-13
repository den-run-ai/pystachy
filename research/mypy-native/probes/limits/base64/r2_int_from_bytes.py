s = b"\x01\x02\x03\x04\x05"
c = int.from_bytes(s)
print(c, c >> 30, (c >> 20) & 0x3ff)
print(c.to_bytes(5), (1 << 39).to_bytes(5))
