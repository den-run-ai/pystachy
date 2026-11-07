<a id="mazepath-shortest-paths-by-breadth-first-search-with-collectionsdeque"></a>

# mazepath: shortest paths with collections.deque

Find the shortest path from `S` to `E` by breadth-first search, keeping cells still
to visit in [`collections.deque`](../../lib/compatibility.md#collections).
The report includes the path length, number of reached cells and farthest cell;
`-p` also draws the path. The source runs under CPython and compiles with Pystachy.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 genmaze.py 1001 1001 > maze.txt
python3 mazepath.py maze.txt
pystachy build mazepath.py -o mazepath
./mazepath maze.txt
python3 genmaze.py 41 21 > small.txt
./mazepath -p small.txt
```

The generator makes deterministic mazes with odd widths and heights. The search
stores cells as `y * width + x`, so its queue and parent list contain integers.
`queue: deque[int] = deque([start])` gives the queue an explicit element type;
`path()` reconstructs a path with `appendleft()`, and `depths()` walks the tree
of parents with another deque.

<a id="speed"></a>
<a id="tests"></a>

## Checks and benchmarks

[`example_mazepath.py`](../../tests/programs/apps/example_mazepath.py) compares
parsing, search, paths and depths on generated mazes and small grids with
CPython. It also exercises `main()` with and without `-p`, unreachable exits
and missing endpoints.

The benchmark generates mazes of 1001 × 1001 and 2001 × 2001 cells. Its timings
include both the initial search and the tree of child lists built for the second
walk; the latter retains a list for each reached cell.

```sh
python3 -I bench.py ../../pystachy 5
```

Generated mazes and the executable go to `build/mazepath/` at the repository root.
[Earlier timings and memory measurements](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/mazepath/README.md#speed)
predate later deque and compiler changes. See the
[benchmark guidance](../README.md#benchmarks) when measuring a current build.
