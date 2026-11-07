# error: tests/ffi/errors/ctypes_before_import.py:2: error: ctypes declarations: import ctypes before declaring a library
lib = ctypes.CDLL(None)
import ctypes
