# Static ctypes cells restrict addresses to [0, 2**63); CPython wraps negative
# integers to unsigned pointer-sized values. See lib/compatibility.md#ctypes.
from ctypes import c_void_p

cell = c_void_p()
print(cell.value, bool(cell))
cell.value = True
print(cell.value, bool(cell))
cell.value = 0
print(cell.value, bool(cell))
try:
    c_void_p(-1)
except OverflowError as error:
    print(error)
try:
    cell.value = -1
except OverflowError as error:
    print(error)
print(cell.value)
