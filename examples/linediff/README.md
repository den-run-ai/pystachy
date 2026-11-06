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
differences compare changed groups separately. The example groups opcodes itself, which
also lets it mark a final line without a newline; the library's `unified_diff()`, which
marks no such line, now compiles too.

<a id="linediff-unified-and-word-diffs-from-difflibs-sequencematcher"></a>
<a id="speed"></a>
<a id="tests"></a>

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_linediff.py`](../../tests/programs/apps/example_linediff.py)
compares unified and word diffs, context sizes, line endings, summaries and
command-line errors with CPython.

The benchmark generates two 50,000-line texts and exercises unified, word and
summary modes. The program retains both texts and the matcher tables.

```sh
python3 -I bench.py ../../pystachy 5
```

Generated inputs and executables go to `build/linediff/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/linediff/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
