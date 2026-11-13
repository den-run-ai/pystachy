# bytes.isascii() and a strict UTF-8 decode of a surrogate's encoding
print(b"abc".isascii(), "é".encode().isascii())
try:
    print(len(b"\xed\xa0\x80".decode()))
except UnicodeDecodeError:
    print("UnicodeDecodeError")
