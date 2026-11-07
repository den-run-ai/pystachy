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

Errors print usage and exit with status 2. `-c` counts Unicode characters under both
Pystachy and CPython.

<a id="cut-fields-and-characters-of-each-line-with-getopts-option-parsing"></a>
<a id="speed"></a>
<a id="tests"></a>

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_cut.py`](../../tests/programs/apps/example_cut.py)
compares range parsing, selection, options, generated input and errors with CPython.

The benchmark generates 500,000 rows and exercises field and character selection,
complement selection and skipped undelimited lines.

```sh
python3 -I bench.py ../../pystachy 5
```

Generated inputs and executables go to `build/cut/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/cut/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
