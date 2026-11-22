"""Collector kernels: the structures they build survive or form the expected cycles."""
import gc_collect
import gc_traversal


def test_gc_collect():
    gc_collect.benchamark_collection(2, 5, 3)
    assert len(gc_collect.TIMED) == 1 and gc_collect.TIMED[0] >= 0.0
    cycles = gc_collect.create_gc_cycles(5, 3)
    assert len(cycles) == 5
    for start in cycles:
        node = start.next
        length = 1
        while node is not start:
            assert node is not None and node.next is not None and node.next.prev is node
            node = node.next
            length += 1
        assert length == 4


def test_gc_traversal():
    node = gc_traversal.benchamark_collection(2, 30)
    assert len(gc_traversal.TIMED) == 1 and gc_traversal.TIMED[0] >= 0.0
    depth = 0
    slots = 0
    while len(node) > 0:
        for item in node:
            assert item is node[0]
        slots += len(node)
        node = node[0]
        depth += 1
    assert (depth, slots) == (29, 435)
