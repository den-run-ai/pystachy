# error: expected bytes, got str
# A binary file's write() takes bytes (CPython raises TypeError: a bytes-like object is required, not 'str')
with open("x.bin", "wb") as f:
    f.write("text")
