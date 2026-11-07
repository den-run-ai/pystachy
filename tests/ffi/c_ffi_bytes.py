# Raw bytes borrow Str's storage during a C call, including high bytes and embedded NULs.
# Returned char pointers are copied; optional bytes preserve NULL separately from b"".
import ffi
from ffi import bytes_at, load_library


@ffi.extern("libpystachy-ffitest.so")
def ffi_bytes_sum(data: bytes, n: ffi.c_size_t) -> ffi.c_uint: ...


@ffi.extern("libpystachy-ffitest.so")
def ffi_bytes_is_null(data: bytes | None) -> ffi.c_int: ...


@ffi.extern("libpystachy-ffitest.so", "ffi_bytes_result")
def binary_result(present: ffi.c_int) -> bytes: ...


@ffi.extern("libpystachy-ffitest.so", "ffi_bytes_result")
def optional_result(present: ffi.c_int) -> bytes | None: ...


@ffi.extern("libpystachy-ffitest.so", "ffi_bytes_result")
def binary_address(present: ffi.c_int) -> ffi.c_void_p: ...


@ffi.extern("libpystachy-ffitest.so")
def ffi_bytes_change(value: ffi.c_int) -> None: ...


payload = b"\x00\xff\x80A\x00"
print(ffi_bytes_sum(payload, len(payload)), ffi_bytes_sum(b"", 0))
print(ffi_bytes_is_null(None), ffi_bytes_is_null(b""), ffi_bytes_is_null(payload))
print(binary_result(1), optional_result(1), optional_result(0))
addr = binary_address(1)
print(bytes_at(addr, -1), bytes_at(addr, 4), ffi.bytes_at(addr, 0), bytes_at(0, 0))
# Independently test copying: mutating the C storage cannot alter the result already returned.
saved = binary_result(1)
ffi_bytes_change(66)
print(saved, binary_result(1))
ffi_bytes_change(255)
# Calls that allocate around the borrowed buffer run under the harness's GC stress too.
total = 0
for i in range(20):
    fresh = b"\xff\x00" * (i + 1)
    total += ffi_bytes_sum(fresh, len(fresh))
    copied = bytes_at(addr, 4)
    total += copied[3]
print(total)
# Explicit opens use the same loader path as @extern, including the current process.
print(load_library("libpystachy-ffitest.so") == ffi.load_library("libpystachy-ffitest.so"))
print(load_library("") != 0)
for k in range(6):
    try:
        if k == 0:
            print(binary_result(0))
        elif k == 1:
            print(bytes_at(0, -1))
        elif k == 2:
            print(bytes_at(0, 1))
        elif k == 3:
            print(bytes_at(addr, -2))
        elif k == 4:
            print(load_library("bad\x00library"))
        else:
            print(ffi.string_at(addr, -1))
    except ValueError as e:
        print(type(e).__name__, e)
try:
    load_library("libpystachy-ctypes-does-not-exist.so")
except OSError:
    print("missing library raised OSError")
