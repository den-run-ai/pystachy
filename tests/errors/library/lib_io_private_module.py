# error: module '_pystachy_io' is not supported: it is Pystachy's own, which its io module imports
from _pystachy_io import default_encoding

print(default_encoding())
