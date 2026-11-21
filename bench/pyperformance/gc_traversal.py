# pystachy: dynamic-any
# Pystachy port: the lists nest to any depth, so they hold dynamic Any values (above);
# pyperf is not imported, and the main below replaces pyperf.Runner.
import gc
import time
from typing import Any

N_LEVELS = 1000


def create_recursive_containers(n_levels):

    current_list: list[Any] = []  # Pystachy port: annotated, like new_list
    for n in range(n_levels):
        new_list: list[Any] = [None] * n
        for index in range(n):
            new_list[index] = current_list
        current_list = new_list

    return current_list


TIMED: list[float] = []  # Pystachy port: the seconds of each timed part


def benchamark_collection(loops, n_levels):
    total_time = 0.0  # Pystachy port: a float from the start
    all_cycles = create_recursive_containers(n_levels)
    for _ in range(loops):
        gc.collect()
        # Main loop to measure
        t0 = time.perf_counter()  # Pystachy port: pyperf.perf_counter()
        collected = gc.collect()
        total_time += time.perf_counter() - t0

        assert collected is None or collected == 0

    TIMED.append(total_time)  # Pystachy port: the seconds, which upstream returns
    return all_cycles  # Pystachy port: the lists, which the main checks


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops and argv[2] the number of levels; the lists that survive the
    # collections are walked outside the timer, and the time goes to stderr.
    import sys
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n_levels = int(sys.argv[2]) if len(sys.argv) > 2 else N_LEVELS
    node = benchamark_collection(loops, n_levels)
    print("seconds", sum(TIMED), file=sys.stderr)
    depth = 0
    slots = 0
    while len(node) > 0:
        for item in node:
            assert item is node[0]
        slots += len(node)
        node = node[0]
        depth += 1
    print("gc_traversal", loops, n_levels, depth, slots)
