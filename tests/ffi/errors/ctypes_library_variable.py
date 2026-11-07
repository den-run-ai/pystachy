# error: tests/ffi/errors/ctypes_library_variable.py:4: error: ctypes declarations: CDLL takes one literal library name or None, without loader options
import ctypes

lib = ctypes.CDLL(path)
