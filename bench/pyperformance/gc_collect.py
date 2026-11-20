# Pystachy port: pyperf is not imported; the main below replaces pyperf.Runner.
import gc
import time

CYCLES = 100
LINKS = 20


class Node:
    def __init__(self):
        self.next = None
        self.prev = None

    def link_next(self, next):
        self.next = next
        self.next.prev = self


def create_cycle(node, n_links):
    """Create a cycle of n_links nodes, starting with node."""

    if n_links == 0:
        return

    current = node
    for i in range(n_links):
        next_node = Node()
        current.link_next(next_node)
        current = next_node

    current.link_next(node)


def create_gc_cycles(n_cycles, n_links):
    """Create n_cycles cycles n_links+1 nodes each."""

    cycles = []
    for _ in range(n_cycles):
        node = Node()
        cycles.append(node)
        create_cycle(node, n_links)
    return cycles


TIMED: list[float] = []  # Pystachy port: the seconds of each timed part


def benchamark_collection(loops, cycles, links):
    total_time = 0.0  # Pystachy port: a float from the start
    for _ in range(loops):
        gc.collect()
        all_cycles = create_gc_cycles(cycles, links)

        # Main loop to measure
        # Pystachy port: rebinding the list drops the cycles as del does; del of a local
        # is rejected in an imported module, and the pytest suite imports this one.
        all_cycles = []
        t0 = time.perf_counter()  # Pystachy port: pyperf.perf_counter()
        collected = gc.collect()
        total_time += time.perf_counter() - t0

        # Pystachy port: Pystachy's collect() returns 0; it does not count what it frees.
        assert collected is None or collected == 0 or collected >= cycles * (links + 1)

    TIMED.append(total_time)  # Pystachy port: the seconds, which upstream returns


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops, argv[2] the cycles and argv[3] the links of each; the nodes
    # of one set of cycles are counted outside the timer, and the time goes to stderr.
    import sys
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cycles = int(sys.argv[2]) if len(sys.argv) > 2 else CYCLES
    links = int(sys.argv[3]) if len(sys.argv) > 3 else LINKS
    benchamark_collection(loops, cycles, links)
    print("seconds", sum(TIMED), file=sys.stderr)
    nodes = 0
    for start in create_gc_cycles(cycles, links):
        node = start.next
        nodes += 1
        while node is not start:
            assert node is not None and node.next is not None and node.next.prev is node
            node = node.next
            nodes += 1
    print("gc_collect", loops, cycles, links, nodes)
