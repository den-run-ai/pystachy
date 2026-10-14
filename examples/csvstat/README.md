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
for the tested data. The compiled reader eagerly retains parsed rows; CPython
reads them incrementally.

<a id="csvstat-the-statistics-of-each-column-of-a-csv-file"></a>
<a id="what-compiling-buys"></a>
<a id="tests"></a>

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. 200,000 orders (16.1 MB); median of 11 alternating process runs after warmup,
including startup; peak RSS of one run. Reader/writer rows are medians from
`rwbench.py`. Runs on the shared host varied by 20% or more.

| | CPython 3.13.16 | Pystachy AOT | speedup |
|---|---:|---:|---:|
| `csvstat.py orders.csv` | 0.825 s | 0.414 s | 2.0× |
| `csvstat.py orders.csv --csv` | 0.774 s | 0.373 s | 2.1× |
| peak RSS | 65.7 MB | 162.2 MB | |
| `csv.reader`, from the file | 1.333 µs/row | 0.850 µs/row | 1.6× |
| `csv.reader`, from lines in memory | 1.221 µs/row | 0.713 µs/row | 1.7× |
| `csv.writer`, to a file | 1.207 µs/row | 0.755 µs/row | 1.6× |

The CSV report was about 2× faster in this baseline, with about 2.5× peak
memory because the subset reader materializes the file.

## Checks and reproduction

`tests/example_csvstat.py` compares reports for 3,000 generated orders and rows
shorter or longer than their header with CPython.

```sh
python3 -I bench.py ../../pystachy 11
```

The benchmark writes generated inputs and executables to `build/csvstat/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
