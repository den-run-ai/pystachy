# error: keyword arguments to bytes.decode() are not supported; pass them by position
print(b"abc".decode(errors="strict", encoding="ascii"))
