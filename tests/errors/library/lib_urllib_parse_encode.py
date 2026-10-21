# error: 'urllib.parse.ParseResult' object has no method 'encode'
# (the method of CPython's _ResultMixinStr, which makes a ParseResultBytes)
from urllib.parse import urlparse

print(urlparse("http://example.com/").encode())
