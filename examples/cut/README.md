# cut: field and character selection

Select fields or character ranges from each input line. Command-line parsing
uses [`getopt.gnu_getopt`](../../lib/compatibility.md#getopt), including GNU-style
long options and options after filenames.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 gentable.py 500000 > table.tsv
python3 cut.py -f 2,5-7 table.tsv
pystachy build cut.py -o cut
./cut table.tsv -f 3 --complement
./cut -c 1-20 table.tsv
```

`-f LIST` selects fields; `-c LIST` selects positions. Lists contain `N`, `N-M`,
`N-` or `-M`, numbered from one (up to 18 digits), separated by commas. Items
print once in input order; a second selection option is an error. `-d DELIM`
sets the field delimiter (tab by default); `-s` skips undelimited lines;
`--complement` inverts selection; `--output-delimiter STR` sets output separation.
The corresponding long forms `--fields`, `--characters`, `--delimiter` and
`--only-delimited`, and unique prefixes such as `--compl`, also work.

Errors print usage and exit with status 2. Outside ASCII, `-c` counts bytes
under Pystachy and Unicode characters under CPython.

<a id="cut-fields-and-characters-of-each-line-with-getopts-option-parsing"></a>
<a id="speed"></a>
<a id="tests"></a>

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. 500,000 rows (31 MB); median wall time of five process runs, including startup;
peak RSS of one run. Other jobs shared the host.

| selection | CPython 3.13.16 | Pystachy AOT | speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|
| `-f 2,5-7` | 0.480 s | 0.376 s | 1.3x | 10.9 MB | 35.4 MB |
| `-f 3 --complement` | 0.545 s | 0.335 s | 1.6x | 10.9 MB | 35.4 MB |
| `-c 1-20` | 0.415 s | 0.270 s | 1.5x | 10.9 MB | 35.9 MB |
| `-s -f 8,1` | 0.393 s | 0.238 s | 1.7x | 11.0 MB | 35.0 MB |

The baseline speedup is 1.3–1.7×; line reading and string operations dominate.
Peak memory is about 3× CPython’s but remains bounded as input grows.

## Checks and reproduction

`tests/example_cut.py` compares range parsing, selection, options, generated
input and errors with CPython.

```sh
python3 -I bench.py ../../pystachy 5
```

The benchmark writes generated inputs and executables to `build/cut/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
