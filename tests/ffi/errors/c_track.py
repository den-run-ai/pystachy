# error: tests/ffi/errors/c_track.py:2: error: cannot import name 'track' from 'ffi': it is internal to Pystachy's lib/pyobj.py
from ffi import track


class A:
    pass


print(track(A(), 5, 0))
