"""CPython exporters used by py_cpu_buffer.py; this file is not compiled."""
import array
import weakref

_last = None
_releases = 0
_exports = 0


class Owner:
    def __init__(self):
        self.data = array.array("d", [1.0, 2.0, 3.0, 4.0])

    def __buffer__(self, flags):
        global _exports
        _exports += 1
        return memoryview(self.data)

    def __release_buffer__(self, view):
        global _releases
        _releases += 1
        view.release()


def make(case):
    data = array.array("d", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    if case == 1:
        return memoryview(data.tobytes()).cast("d")
    if case == 2:
        return memoryview(data)[::2]
    if case == 3:
        return memoryview(data)[::-1]
    if case == 4:
        return memoryview(data).cast("B").cast("d", shape=[2, 3])
    if case == 5:
        return data.tobytes()
    if case == 6:
        return array.array("f", [1.0, 2.0])
    if case == 7:
        return array.array("d")
    if case == 8:
        return memoryview(data)[2:5]
    if case == 9:
        # Native memcpy reads must support legal but unaligned buffer addresses.
        return memoryview(bytearray(b"x" + data.tobytes()))[1:].cast("d")
    return data


def watched():
    global _last
    owner = Owner()
    _last = weakref.ref(owner)
    return owner


def alive():
    return _last is not None and _last() is not None


def releases():
    return _releases


def exports():
    return _exports


def resize():
    # A live export must prevent relocation; once all views close, append works.
    _last().data.append(9.0)


def mutate():
    _last().data[1] = 20.0


def numeric(case):
    pairs = [
        ([1e16, 1.0, -1e16], [1.0, 1.0, 1.0]),
        ([-1.0, 1.0 + 2.0**-27], [1.0, 1.0 - 2.0**-27]),
        ([float("nan")], [1.0]),
        ([float("inf")], [1.0]),
        ([float("inf"), -float("inf")], [1.0, 1.0]),
        ([-0.0], [1.0]),
        ([0.0], [float("inf")]),
        ([1e308], [1e308]),
    ]
    return [array.array("d", xs) for xs in pairs[case]]
