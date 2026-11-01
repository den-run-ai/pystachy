import _pystachy_bytescan
from _pystachy_bytescan import scan as other_scan


print(_pystachy_bytescan.scan(b"quote\"tail", 1, 7, 34, 92, 32))
print(other_scan(b"", 0, 0, 1, 2, 0))
