# chr() of a surrogate (U+D800..U+DFFF) is its three-byte UTF-8-style form, which print() writes as
# it is; CPython's strict UTF-8 stdout raises UnicodeEncodeError ("surrogates not allowed"). Its
# repr() and ord() are CPython's.
c = chr(0xD800)
print(repr(c), ord(c), ascii(chr(0xDFFF)))
print(c)
