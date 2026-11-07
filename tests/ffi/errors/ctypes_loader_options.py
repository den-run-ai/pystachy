# error: tests/ffi/errors/ctypes_loader_options.py:4: error: ctypes declarations: CDLL takes one literal library name or None, without loader options
import ctypes

lib = ctypes.CDLL(None, use_errno=True)
