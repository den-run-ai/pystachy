# A direct byref borrow must not instantiate ctypes' owning _Pointer wrapper.
# No stored byref appears here: its allocating helper must remain unreachable.
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_pointer_alias.argtypes = [ct.POINTER(ct.c_void_p), ct.POINTER(ct.c_void_p)]
lib.ffi_pointer_alias.restype = ct.c_int


def immediate(cell: ct.c_void_p) -> int:
    return lib.ffi_pointer_alias(ct.byref(cell), ct.byref(cell))


print(immediate(ct.c_void_p()))
