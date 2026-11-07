# Imported aliases, tuple prototypes and generated annotations survive ordinary
# module variables named like Python builtins.
from ctypes import CDLL as Library, c_int32 as Int32, c_void_p as Address, POINTER as Ptr, byref as ref, string_at as read

lib = Library("libpystachy-ffitest.so")
lib.ffi_echo_int.restype = Int32
lib.ffi_echo_int.argtypes = (Int32,)
lib.ffi_pointer_set.argtypes = [Ptr(Address)]
lib.ffi_pointer_set.restype = None

int = 7
float = 2.5
bytes = b"ordinary variable"
list = 9
print(lib.ffi_echo_int(4294967295), int, float, bytes, list)
cell = Address()
lib.ffi_pointer_set(ref(cell))
print(read(cell.value, 4))
