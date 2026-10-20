# error: lib_io_bytesio_str.py:5: error: expected bytes | None, got str
# lib/io's BytesIO holds bytes: CPython raises TypeError for a str, as its write() does (and so
# print(..., file=) to a BytesIO, which writes strs)
from io import BytesIO
b = BytesIO("1234567890")
print(b.getvalue())
