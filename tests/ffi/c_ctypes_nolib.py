# Opening an unused CDLL still fails at that statement, after earlier imports.
import ctypes
import side_noisy

unused = ctypes.CDLL("libpystachy-no-such-library.so.9")

print("not reached")
