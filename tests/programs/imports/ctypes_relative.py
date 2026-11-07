# A package-relative module called ctypes belongs to that package, even when
# its objects happen to use CDLL, argtypes and restype as attribute names.
import ctypes_relative_pkg.use
