# CPython 3.13.16 Lib/test/test_heapq.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 ab72726259119159f060aa80274efb33e53a5455636bd5aa16f923535375b348),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: TestHeapPython.test_heappop_max, TestHeapPython.test_heapsort.
"""Unittests for heapq."""
import random
import heapq as py_heapq

class TestHeap:

    def check_invariant(self, heap):
        for pos, item in enumerate(heap):
            if pos:
                parentpos = pos - 1 >> 1
                assert heap[parentpos] <= item

    def heapiter(self, heap):
        try:
            while 1:
                yield py_heapq.heappop(heap)
        except IndexError:
            pass

    def test_heappop_max(self):
        h = [3, 2]
        assert py_heapq._heappop_max(h) == 3
        assert py_heapq._heappop_max(h) == 2

    def test_heapsort(self):
        for trial in range(100):
            size = random.randrange(50)
            data = [random.randrange(25) for i in range(size)]
            if trial & 1:
                heap = data[:]
                py_heapq.heapify(heap)
            else:
                heap = []
                for item in data:
                    py_heapq.heappush(heap, item)
            heap_sorted = [py_heapq.heappop(heap) for i in range(size)]
            assert heap_sorted == sorted(data)

class TestHeapPython(TestHeap):
    pass


def _TestHeapPython__test_heappop_max():
    t = TestHeapPython()
    t.test_heappop_max()
    print('ok TestHeapPython.test_heappop_max')


def _TestHeapPython__test_heapsort():
    t = TestHeapPython()
    t.test_heapsort()
    print('ok TestHeapPython.test_heapsort')


_TestHeapPython__test_heappop_max()
_TestHeapPython__test_heapsort()
