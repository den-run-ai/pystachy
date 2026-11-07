"""Optional real NumPy protocol checks; no compiler or NumPy dependency in CI."""
import gc
import unittest
import weakref
from unittest.mock import patch

from pystachy_dlpack import from_dlpack_f64

try:
    import numpy as np
except ImportError:
    np = None


class DLPackOnly:
    """Deliberately has no Python buffer protocol or array conversion hook."""

    def __init__(self, array, device=(1, 0)):
        self.array = array
        self.device = device
        self.exports = []

    def __dlpack_device__(self):
        return self.device

    def __dlpack__(self, **kwargs):
        self.exports.append(kwargs)
        return self.array.__dlpack__(**kwargs)


class DeviceContract(unittest.TestCase):
    def test_reject_device_before_requesting_capsule_or_importing_numpy(self):
        for device in ((2, 0), (3, 0), (1, 1)):
            with self.subTest(device=device), patch.dict("sys.modules", {"numpy": None}):
                source = DLPackOnly(None, device)
                with self.assertRaisesRegex(BufferError, "CPU device 0"):
                    from_dlpack_f64(source)
                self.assertEqual(source.exports, [])

    def test_numpy_is_optional_until_cpu_import(self):
        with patch.dict("sys.modules", {"numpy": None}):
            with self.assertRaises(ModuleNotFoundError):
                from_dlpack_f64(DLPackOnly(None))


@unittest.skipUnless(np is not None, "optional NumPy >= 2.1 is required")
class DLPackContract(unittest.TestCase):
    def test_alias_offset_and_readonly(self):
        owner = np.arange(8, dtype="d")
        source = DLPackOnly(owner[2:6])
        with self.assertRaises(TypeError):
            memoryview(source)
        view = from_dlpack_f64(source)
        self.assertEqual(view.ctypes.data, owner.ctypes.data + 16)
        self.assertTrue(np.shares_memory(view, owner))
        self.assertEqual(len(source.exports), 1)
        self.assertIs(source.exports[0]["copy"], False)
        self.assertFalse(view.flags.writeable)
        self.assertTrue(memoryview(view).readonly)
        with self.assertRaises(ValueError):
            view[0] = 99.0
        owner[2] = 42.0
        self.assertEqual(view[0], 42.0)

    def test_readonly_producer(self):
        owner = np.array([1., 2.])
        owner.setflags(write=False)
        view = from_dlpack_f64(DLPackOnly(owner))
        self.assertTrue(np.shares_memory(view, owner))
        self.assertFalse(view.flags.writeable)

    def test_empty_and_singleton(self):
        for owner in (np.empty(0, dtype="d"), np.arange(4, dtype="d")[::3][:1]):
            with self.subTest(shape=owner.shape):
                view = from_dlpack_f64(DLPackOnly(owner))
                self.assertEqual(view.shape, owner.shape)
                with memoryview(view) as exported:
                    self.assertEqual(exported.strides, (8,))

    def test_layout_rejections_release_consumed_owner(self):
        cases = ((np.arange(4, dtype="f"), TypeError),
                 (np.arange(4, dtype="i8"), TypeError),
                 (np.zeros((2, 2), dtype="d"), ValueError),
                 (np.array(2., dtype="d"), ValueError),
                 (np.arange(4, dtype="d")[::2], ValueError),
                 (np.arange(4, dtype="d")[::-1], ValueError))
        for owner, error in cases:
            with self.subTest(dtype=owner.dtype, shape=owner.shape, strides=owner.strides):
                with self.assertRaises(error):
                    from_dlpack_f64(DLPackOnly(owner))
        # This owned 2D allocation has no surviving outer case-table reference.
        owner = np.zeros((2, 2), dtype="d")
        released = []
        weakref.finalize(owner, released.append, "owner")
        source = DLPackOnly(owner)
        with self.assertRaises(ValueError):
            from_dlpack_f64(source)
        del source, owner
        gc.collect()
        self.assertEqual(released, ["owner"])

    def test_non_native_dtype_is_not_converted(self):
        owner = np.arange(4, dtype="d").astype(">f8" if np.little_endian else "<f8")
        with self.assertRaises((BufferError, TypeError)):
            from_dlpack_f64(DLPackOnly(owner))

    def test_owner_survives_producer_and_releases_with_last_view(self):
        owner = np.array([1., 2., 3.])
        released = []
        weakref.finalize(owner, released.append, "owner")
        owner_ref = weakref.ref(owner)
        source = DLPackOnly(owner)
        source_ref = weakref.ref(source)
        view = from_dlpack_f64(source)
        child = view[1:]
        del source, owner, view
        gc.collect()
        self.assertIsNone(source_ref())
        self.assertIsNotNone(owner_ref())
        self.assertEqual(released, [])
        self.assertEqual(child.tolist(), [2., 3.])
        del child
        gc.collect()
        self.assertIsNone(owner_ref())
        self.assertEqual(released, ["owner"])

    def test_capsule_cannot_be_consumed_twice(self):
        owner = np.array([1., 2.])
        capsule = owner.__dlpack__()

        class OneShot:
            def __init__(self, capsule):
                self.capsule = capsule

            def __dlpack_device__(self):
                return (1, 0)

            def __dlpack__(self, **kwargs):
                return self.capsule

        source = OneShot(capsule)
        first = from_dlpack_f64(source)
        with self.assertRaises(ValueError):
            from_dlpack_f64(source)
        self.assertEqual(first.tolist(), [1., 2.])
        # Dropping the consumed capsule must not release the live consumer.
        del source, capsule, owner
        gc.collect()
        self.assertEqual(first.tolist(), [1., 2.])

    def test_producer_errors_propagate(self):
        class CannotShare:
            def __dlpack_device__(self):
                return (1, 0)

            def __dlpack__(self, **kwargs):
                raise BufferError("producer cannot share this allocation")

        with self.assertRaisesRegex(BufferError, "producer cannot share"):
            from_dlpack_f64(CannotShare())


if __name__ == "__main__":
    unittest.main()
