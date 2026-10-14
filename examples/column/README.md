# column: aligned tables

Align table cells to their widest column and build the output with
[`io.StringIO`](../../lib/compatibility.md#io). The same source runs under CPython
and compiles with Pystachy.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 gentable.py 300000 > table.tsv
python3 column.py table.tsv
pystachy build column.py -o column
./column -R 1,6,7 table.tsv
```

`-s SEP` chooses the input delimiter (tab by default); `-o SEP` chooses the
output separator (two spaces); `-R COLS` right-aligns columns numbered from one.
The last cell is padded only when right-aligned. Widths count bytes under
Pystachy and Unicode characters under CPython.

<a id="column-aligned-columns-built-in-an-iostringio"></a>
<a id="speed"></a>
<a id="tests"></a>

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. 300,000 rows (20 MB); median wall time of five process runs, including startup;
peak RSS of one run. The shared host produced up to 2× variation in CPython
times, so the apparent 4× speedup is especially noisy.

| options | CPython 3.13.16 | Pystachy AOT | speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|
| (none) | 1.518 s | 0.376 s | 4.0x | 232.4 MB | 230.1 MB |
| `-R 1,5,6,7` | 0.779 s | 0.381 s | 2.0x | 232.7 MB | 230.9 MB |
| `-o ' \| '` | 1.024 s | 0.487 s | 2.1x | 237.6 MB | 236.2 MB |

Both programs retain the entire table, which dominates memory use.

## Checks and reproduction

`tests/example_column.py` compares widths, alignment, options, generated tables
and error cases with CPython.

```sh
python3 -I bench.py ../../pystachy 5
```

The benchmark writes generated inputs and executables to `build/column/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
