# csvstat: CSV column reports

Report column types, counts, empty/distinct values, most common values, ranges
and numeric statistics. The example uses the subset
[`csv`](../../lib/compatibility.md#csv) implementation, including quoted commas,
escaped quotes and multiline fields.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 gencsv.py 200000 > orders.csv
python3 csvstat.py orders.csv
pystachy build csvstat.py -o csvstat
./csvstat orders.csv --csv
```

The default is a text report; `--csv` emits the same statistics as CSV.
`gencsv.py` produces deterministic input. Both runtimes produce the same report
for the tested data. Both readers consume rows incrementally. The report still
retains per-column value counts and numeric samples for its statistics.

<a id="csvstat-the-statistics-of-each-column-of-a-csv-file"></a>
<a id="what-compiling-buys"></a>
<a id="tests"></a>

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_csvstat.py`](../../tests/programs/apps/example_csvstat.py)
compares reports for 3,000 generated orders and rows shorter or longer than their
header with CPython.

The benchmark generates 200,000 orders, times text and CSV reports, and uses
[`rwbench.py`](rwbench.py) to time the reader and writer separately, including parsing
lines already in memory.

```sh
python3 -I bench.py ../../pystachy 11
```

Generated inputs and executables go to `build/csvstat/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/csvstat/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
