# column: aligned columns, built in an io.StringIO

`column.py` aligns the columns of a table, as `column -t` does: it splits each line into cells,
pads each column to its widest cell and joins the cells with a separator. It is ordinary Python,
which CPython runs as it is and Pystachy compiles as it is, and it builds its output in the
standard library's `io.StringIO` ([`lib/io`](../../lib/README.md#io-pystachys-own)), a line at a
time with `print(..., file=out)`, then writes it out at once with `out.getvalue()`:

```
$ python3 gentable.py 300000 > table.tsv      # id, date, host, path, status, bytes, ms
$ python3 column.py table.tsv                 # CPython
$ pystachy build column.py -o column && ./column -R 1,6,7 table.tsv
     0  2026-10-14  web7               /                               500     36  133.08
     1  2026-10-06  web7               /favicon.ico                    200      9  469.75
     2  2026-10-05  db1                /                               304      1  998.37
...
$ ./column -s , -o ' | ' table.csv
```

- `-s SEP` splits the lines at SEP (a tab by default), `-o SEP` joins the cells (two spaces by
  default), and `-R COLS` right-aligns the columns it names (`1,6,7`: numbered from 1). The last
  cell of a line is not padded, unless it is right-aligned.
- `print(line, file=out)` writes each line into the `StringIO`: Pystachy passes each piece of a
  `print()` to the `write()` method of the object it is given, as CPython does, and the
  `StringIO` keeps the pieces in a list that `getvalue()` joins once.

CPython and the executable print the same table. Past ASCII, the widths count a cell's bytes under
Pystachy, whose strings are UTF-8, and its characters under CPython.

## Speed

`bench.py`, on a 4-core x86-64 VM: median wall time of 5 runs with process start-up, peak RSS of
one, a table of 300,000 lines (20 MB). The executable is Pystachy's AOT build of `column.py`. Two
other jobs shared the machine, and CPython's times varied by up to 2 times between runs of the
same command; the table is the median run of two.

| options | CPython 3.13.16 | Pystachy AOT | speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|
| (none) | 1.518 s | 0.376 s | 4.0x | 232.4 MB | 230.1 MB |
| `-R 1,5,6,7` | 0.779 s | 0.381 s | 2.0x | 232.7 MB | 230.9 MB |
| `-o ' \| '` | 1.024 s | 0.487 s | 2.1x | 237.6 MB | 236.2 MB |

- **Compiled, `column` is 2 to 4 times as fast as CPython.** It holds the whole table (both
  programs peak at about 230 MB), makes a list of cells per line, then a padded str per cell and a
  line per row; the padding and joining are where the compiled code gains.
- **The `StringIO` is cheap in both**: 300,000 `print()` calls into it, each two `write()` calls
  (the line and its newline), then one `getvalue()`.
- Building the executable takes about 1 s.

## Tests

`tests/example_column.py` runs `widths()`, `align()` (into a `StringIO`) and `parse_columns()` on
their edge cases, and `main()` on generated tables with each option, then with each error, and
compares what it prints with CPython's (`tests/example_column.path` puts this directory on the
module path). `bench.py` runs the table above: `python3 -I bench.py ../../pystachy 5`, from
anywhere; it writes its table and executable to `build/column/`.
