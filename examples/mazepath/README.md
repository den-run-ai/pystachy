# mazepath: shortest paths by breadth-first search, with collections.deque

`mazepath.py` finds the shortest path through a maze: it searches the grid breadth first from `S`,
keeping the cells still to visit in a `collections.deque`
([`lib/collections`](../../lib/README.md#collections-pystachys-own)), and prints the length of the
shortest path to `E`, how many cells it reached and the farthest of them; `-p` draws the path. It
is ordinary Python, which CPython runs as it is and Pystachy compiles as it is:

```
$ python3 genmaze.py 1001 1001 > maze.txt     # a perfect maze, with one wall in 8 knocked out
$ python3 mazepath.py maze.txt                # CPython
$ pystachy build mazepath.py -o mazepath && ./mazepath maze.txt
1001x1001 maze, 531133 cells reached, the farthest 2424 steps away at (991, 995)
shortest path from S to E: 2412 steps
$ ./mazepath -p small.txt
41x21 maze, 425 cells reached, the farthest 82 steps away at (39, 13)
shortest path from S to E: 80 steps
#########################################
#S#.........#.#...............#.....#...#
#*#.#####.#.#.#.###########.#.###.#.#.#.#
#*#.......#.....#...........#...#.#.#.#.#
...
```

- The search's queue is typed where it is made, `queue: deque[int] = deque([start])`: Pystachy's
  `deque` is a generic class, and its items' type comes from the iterable it is made from, the
  annotation of where it goes, or the call (`deque[int]()`). `path()` builds the path backwards
  with `appendleft()`, and `depths()` walks the tree of parents breadth first with another deque.
- Cells are numbered `y * width + x`, so the deque holds ints, and `parent` is a flat list.

CPython and the executable print the same report and the same drawing.

## Speed

`bench.py`, on a 4-core x86-64 VM: median wall time of 5 runs with process start-up, peak RSS of
one, mazes of 1001 x 1001 and 2001 x 2001 cells. The executable is Pystachy's AOT build of
`mazepath.py`.

| maze | CPython 3.13.16 | Pystachy AOT | speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|
| 1001 x 1001 | 0.832 s | 0.228 s | 3.7x | 140.3 MB | 127.0 MB |
| 2001 x 2001 | 4.296 s | 1.558 s | 2.8x | 535.1 MB | 584.8 MB |

- **The search itself is 5 times as fast compiled**: timed alone, the breadth-first search of the
  2001 x 2001 maze, 2.1 million cells through the deque, takes 0.20 s, against 1.03 s with
  CPython's C deque. Pystachy's deque is written in the subset: two typed lists, one for each end,
  which pops from and appends to its own.
- **The rest is the dict of children lists** that `depths()` builds for its second walk, a list
  per reached cell, which dominates the larger maze in both programs and its memory.
- Building the executable takes under 1 s.

## Tests

`tests/example_mazepath.py` runs `parse()`, `search()`, `path()` and `depths()` on generated
mazes and small grids, and `main()` with and without `-p`, on a maze without a path and on one
without `E`, and compares what it prints with CPython's (`tests/example_mazepath.path` puts this
directory on the module path). `bench.py` runs the table above:
`python3 -I bench.py ../../pystachy 5`, from anywhere; it writes its mazes and executable to
`build/mazepath/`.
