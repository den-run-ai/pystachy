# linediff: line and word differences

Compare two text files using
[`difflib.SequenceMatcher`](../../lib/compatibility.md#difflib). It emits unified
diffs, word changes or a summary from matcher opcodes.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 gentext.py 50000 old > old.txt
python3 gentext.py 50000 new > new.txt
python3 linediff.py old.txt new.txt
pystachy build linediff.py -o linediff
./linediff -U 1 old.txt new.txt
./linediff --words old.txt new.txt
```

`-U N` sets unified-diff context (default 3); `--words` marks changed words;
`-q` reports similarity and change counts. Exit status is 0 for identical files,
1 for differences and 2 for errors.

Line endings are preserved, and a final line without a newline is marked. Word
differences compare changed groups separately. The example groups opcodes itself
because the library’s `unified_diff` generator does not compile.

<a id="linediff-unified-and-word-diffs-from-difflibs-sequencematcher"></a>
<a id="speed"></a>
<a id="tests"></a>

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. Two 50,000-line texts (2.3 MB each); median wall time of five process runs,
including startup; peak RSS of one run.

| mode | CPython 3.13.16 | Pystachy AOT | speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|
| unified | 0.167 s | 0.079 s | 2.1x | 35.0 MB | 51.4 MB |
| `--words` | 0.190 s | 0.086 s | 2.2x | 35.0 MB | 54.9 MB |
| `-q` | 0.161 s | 0.076 s | 2.1x | 35.2 MB | 51.3 MB |

The baseline diff runs about 2× faster compiled; both programs retain the
texts and matcher tables. Output is compared with CPython.

## Checks and reproduction

`tests/example_linediff.py` compares unified/word diffs, context sizes,
line-ending cases, summaries and command-line errors with CPython.

```sh
python3 -I bench.py ../../pystachy 5
```

The benchmark writes generated inputs and executables to `build/linediff/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
