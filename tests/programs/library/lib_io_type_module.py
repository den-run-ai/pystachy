# The classes lib's io defines are the C module _io's in CPython: their module is _io, whether a
# program reaches them through io or _io, and so is their objects' default repr.
import io
import _io

print(type(io.StringIO()).__module__, type(io.BytesIO()).__module__)
print(type(io.TextIOWrapper(io.BytesIO())).__module__)
print(type(io.IncrementalNewlineDecoder(None, True)).__module__)
print(type(_io.StringIO()).__module__, type(_io.BytesIO()).__module__)
print(type(io.StringIO()).__name__, type(_io.TextIOWrapper(_io.BytesIO())).__qualname__)
r = repr(io.StringIO())
print(r[: r.find(" at ")])
