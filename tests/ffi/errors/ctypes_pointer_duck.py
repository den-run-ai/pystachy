# error: expected _Pointer, got Fake
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_pointer_set.argtypes = [ct.POINTER(ct.c_void_p)]
lib.ffi_pointer_set.restype = None


class Fake:
    def __init__(self, cell: ct.c_void_p):
        self._cell = cell


lib.ffi_pointer_set(Fake(ct.c_void_p()))
