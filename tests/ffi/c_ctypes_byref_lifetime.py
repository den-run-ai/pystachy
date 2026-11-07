import ctypes as ct
from ctypes import byref as borrow

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_pointer_set.argtypes = [ct.POINTER(ct.c_void_p)]
lib.ffi_pointer_set.restype = None
lib.ffi_pointer_alias.argtypes = [ct.POINTER(ct.c_void_p), ct.POINTER(ct.c_void_p)]
lib.ffi_pointer_alias.restype = ct.c_int


def new_cell(label: str) -> ct.c_void_p:
    print(label)
    noise = ["temporary " + str(i) for i in range(32)]
    print(len(noise), noise[-1])
    return ct.c_void_p()


def cell_argument(cell: ct.c_void_p, label: str) -> ct.c_void_p:
    print(label)
    noise = ["later " + str(i) for i in range(32)]
    print(len(noise), noise[-1])
    return cell


def escaped_ref():
    cell = ct.c_void_p()
    return ct.byref(cell)


def replacement(cell: ct.c_void_p):
    print("replacement")
    return borrow(cell)


def shadowed(borrow, cell: ct.c_void_p) -> None:
    print(lib.ffi_pointer_alias(borrow(cell), ct.byref(cell)))


cell = ct.c_void_p()
other = ct.c_void_p()
ref = ct.byref(cell)
print(lib.ffi_pointer_alias(cell, cell))
print(lib.ffi_pointer_alias(ct.byref(cell), ct.byref(cell)))
print(lib.ffi_pointer_alias(ct.byref(cell), ct.byref(other)))
print(lib.ffi_pointer_alias(ref, ct.byref(cell)))
print(lib.ffi_pointer_alias(ct.byref(cell), ref))
print(lib.ffi_pointer_alias(ref, ct.byref(other)))
print(lib.ffi_pointer_alias(ct.byref(other), ref))
lib.ffi_pointer_set(ct.byref(cell))
print(ct.string_at(cell.value, 4))
cell.value = None
lib.ffi_pointer_set(cell)
print(ct.string_at(cell.value, 4))

print(lib.ffi_pointer_alias(ct.byref(new_cell("first")), ct.byref(new_cell("second"))))
print(lib.ffi_pointer_alias(ct.byref(cell_argument(cell, "left")), ct.byref(cell_argument(cell, "right"))))
shadowed(replacement, cell)

# The reference alone keeps the local cell and its native storage alive.
refs = [escaped_ref() for i in range(32)]
noise = ["after return " + str(i) for i in range(32)]
print(len(noise), noise[-1])
for retained in refs:
    lib.ffi_pointer_set(retained)
    if lib.ffi_pointer_alias(retained, retained) != 1:
        raise AssertionError("an escaped reference lost its cell")
print(len(refs))
