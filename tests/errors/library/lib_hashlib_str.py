# error: expected bytes, got str
# lib/hashlib hashes bytes (lib/compatibility.md): for a str, CPython raises TypeError (Strings
# must be encoded before hashing)
import hashlib

print(hashlib.sha1("pystachy").hexdigest())
