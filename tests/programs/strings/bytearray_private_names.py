# CPython's bytearray has its methods and no other attribute: hasattr() and getattr() see none of
# the fields or helpers of lib's class.
b = bytearray(b"ab")
print(hasattr(b, "_b"), hasattr(b, "_n"), hasattr(b, "_getslice"), hasattr(b, "append"), hasattr(b, "__len__"))
print(getattr(b, "_n", "missing"), getattr(b, "upper")())
