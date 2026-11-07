"""Optional CPython DLPack bridge for the retained ``pyobj.Buffer`` prototype.

NumPy >= 2.1 is required only when this helper is called. The result can be
published by a host module and acquired with ``Object.buffer_f64()``. NumPy
owns the consumed DLPack tensor; the retained Py_buffer keeps its view alive.
"""


def from_dlpack_f64(source):
    """Return a read-only, zero-copy CPU float64 view, or reject the input.

    Accept a DLPack producer, not a raw capsule. Require CPU device 0, one
    dimension and contiguous native doubles. Unsupported layouts are rejected
    without casting, flattening or copying. Each call requests a fresh capsule;
    NumPy validates and consumes it once and handles the producer's deleter.
    Other writable aliases remain writable; callers must synchronize writers.
    """
    if source.__dlpack_device__() != (1, 0):  # DLPack kDLCPU
        raise BufferError("DLPack buffer requires CPU device 0")

    import numpy as np

    view = np.from_dlpack(source, copy=False)
    if view.dtype != np.dtype("d"):
        raise TypeError("DLPack buffer requires native float64")
    if view.ndim != 1:
        raise ValueError("DLPack buffer requires one dimension")
    # Check the actual Py_buffer metadata used by Object.buffer_f64(). NumPy
    # normalizes empty/singleton strides when exporting the buffer protocol.
    with memoryview(view) as exported:
        if exported.strides != (8,):
            raise ValueError("DLPack buffer requires contiguous storage")
    view.setflags(write=False)
    return view
