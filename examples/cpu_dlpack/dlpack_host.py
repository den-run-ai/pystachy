"""CPython-only batch producer and lifetime assertions for dlpack_score.py."""
import gc
import weakref

import numpy as np

from pystachy_dlpack import from_dlpack_f64


class Producer:
    # The bridge must use DLPack: this object has no Py_buffer / __array__ hook.
    def __init__(self, array):
        self.array = array

    def __dlpack_device__(self):
        return self.array.__dlpack_device__()

    def __dlpack__(self, **kwargs):
        return self.array.__dlpack__(**kwargs)


_owners = [np.array([99., 1., 2., 3., 4., 99.]), np.array([.25, .5, .75, 1.])]
_refs = [weakref.ref(owner) for owner in _owners]
_releases = []
for i, owner in enumerate(_owners):
    weakref.finalize(owner, _releases.append, i)
del owner

data = from_dlpack_f64(Producer(_owners[0][1:-1]))
weights = from_dlpack_f64(Producer(_owners[1]))
assert data.ctypes.data == _owners[0].ctypes.data + 8
assert weights.ctypes.data == _owners[1].ctypes.data
assert np.shares_memory(data, _owners[0]) and np.shares_memory(weights, _owners[1])
assert not data.flags.writeable and not weights.flags.writeable


def mutate():
    _owners[0][1] = 5.0


def drop():
    global data, weights
    data = weights = None
    _owners.clear()
    gc.collect()


def retained():
    gc.collect()
    return all(ref() is not None for ref in _refs) and not _releases


def released():
    gc.collect()
    return all(ref() is None for ref in _refs) and sorted(_releases) == [0, 1]
