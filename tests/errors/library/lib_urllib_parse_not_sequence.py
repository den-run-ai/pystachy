# error: unsupported call len(int)
# (CPython raises TypeError: not a valid non-string sequence or mapping object)
from urllib.parse import urlencode

print(urlencode(5))
