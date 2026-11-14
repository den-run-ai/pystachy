# error: has no attribute 'get_objects'
# gc has collect() and CPython's settings; the functions that list CPython's objects are not there.
import gc

print(len(gc.get_objects()))
