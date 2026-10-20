# error: name 'warnings' is not defined
# (splittype(), the other split functions and to_bytes() are deprecated, and warn with warnings, which urllib.parse imports in CPython only)
from urllib.parse import splittype

print(splittype("http://example.com/"))
