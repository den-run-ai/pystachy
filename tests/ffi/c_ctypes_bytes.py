# Binary strings, NULLs, copied returns and aliased pointer-sized output cells.
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_ctypes_bytes_sum.argtypes = [ct.c_char_p, ct.c_int]
lib.ffi_ctypes_bytes_sum.restype = ct.c_uint
lib.ffi_bytes_result.argtypes = [ct.c_int]
lib.ffi_bytes_result.restype = ct.c_char_p
lib.ffi_bytes_is_null.argtypes = [ct.c_char_p]
lib.ffi_bytes_is_null.restype = ct.c_int
lib.ffi_bytes_change.argtypes = [ct.c_int]
lib.ffi_bytes_change.restype = None
lib.ffi_pointer_echo.argtypes = [ct.c_void_p]
lib.ffi_pointer_echo.restype = ct.c_void_p
lib.ffi_pointer_set.argtypes = [ct.POINTER(ct.c_void_p)]
lib.ffi_pointer_set.restype = None
lib.ffi_pointer_alias.argtypes = [ct.POINTER(ct.c_void_p), ct.POINTER(ct.c_void_p)]
lib.ffi_pointer_alias.restype = ct.c_int


def binary_argument() -> bytes:
    print("bytes argument")
    return b"\xff\x80\x00A"


def length_argument() -> int:
    print("length argument")
    return 4


print(lib.ffi_ctypes_bytes_sum(binary_argument(), length_argument()))
print(lib.ffi_bytes_is_null(None), lib.ffi_bytes_is_null(b""), lib.ffi_ctypes_bytes_sum(None, 0))
print(lib.ffi_bytes_result(0), lib.ffi_pointer_echo(None), lib.ffi_pointer_echo(0))
print(ct.string_at(None, 0), ct.string_at(0, 0))

cell = ct.c_void_p()
other = ct.c_void_p(0)
print(cell.value, other.value)
ref = ct.byref(cell)
print(lib.ffi_pointer_alias(ref, ct.byref(cell)), lib.ffi_pointer_alias(ref, ct.byref(other)))
print(lib.ffi_pointer_set(ref))
address = cell.value
assert address is not None
assert lib.ffi_pointer_echo(address) == address
other.value = address
assert other.value == cell.value
other.value = None
print(other.value)
other.value = 0
print(other.value)

text = lib.ffi_bytes_result(1)
binary = ct.string_at(address, 4)
print(text, binary, ct.string_at(address))
lib.ffi_bytes_change(65)
print(text, binary, ct.string_at(address, 4))
assert text == b"\xff\x80"
assert binary == b"\xff\x80\x00A"
lib.ffi_bytes_change(255)

# Fresh wrappers and allocations must not invalidate the borrowed storage. The
# suite runs both native modes with collection on every seventh allocation.
for iteration in range(30):
    current = ct.c_void_p()
    current_ref = ct.byref(current)
    noise = [str(iteration), str(iteration + 1), str(iteration + 2)]
    lib.ffi_pointer_set(current_ref)
    assert ct.string_at(current.value, 4) == binary
    assert lib.ffi_pointer_alias(current_ref, ct.byref(current)) == 1
    assert len(noise) == 3
print("30 pointer cells survived allocations")
