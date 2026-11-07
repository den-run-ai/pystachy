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
The last cell is padded only when right-aligned. Widths count Unicode characters
under both Pystachy and CPython.

<a id="column-aligned-columns-built-in-an-iostringio"></a>
<a id="speed"></a>
<a id="tests"></a>

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_column.py`](../../tests/programs/apps/example_column.py)
compares widths, alignment, options, generated tables and error cases with CPython.

The benchmark generates 300,000 rows and exercises alignment and separator options.
The program retains the entire table to determine column widths.

```sh
python3 -I bench.py ../../pystachy 5
```

Generated inputs and executables go to `build/column/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/column/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
