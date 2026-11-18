# error: urllib.parse._unquote_impl() is not supported: parameter 'string': bytes in a closed union is not supported (use scalar, list/dict or native class/file types)
# (it returns bytes, which Pystachy has not; quote_from_bytes() takes them)
from urllib.parse import unquote_to_bytes

print(unquote_to_bytes("abc%20def"))
