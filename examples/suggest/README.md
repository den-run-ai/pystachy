# suggest: spelling suggestions

Find vocabulary matches for unknown words with
[`difflib.get_close_matches`](../../lib/compatibility.md#difflib).

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 genvocab.py vocab 20000 > vocab.txt
python3 genvocab.py text 20000 25 > text.txt
python3 suggest.py vocab.txt text.txt
pystachy build suggest.py -o suggest
./suggest vocab.txt text.txt
```

Words are lowercased and stripped of surrounding punctuation; numbers are
ignored. `-n` sets the number of suggestions (default 3), and `-c` sets the
similarity cutoff (default 0.75, valid range 0–1).

Exit status is 0 when all words are known, 1 when unknown words remain, and 2
for invalid arguments or other errors. Generated inputs and tested reports are
deterministic.

<a id="suggest-spelling-corrections-from-a-vocabulary-with-difflibs-get_close_matches"></a>
<a id="speed"></a>
<a id="tests"></a>

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_suggest.py`](../../tests/programs/apps/example_suggest.py)
compares tokenization, generated vocabularies and text, small cases, options and
errors with CPython.

The benchmark uses a 20,000-word vocabulary and texts of 25 and 100 lines.
Each unknown word is matched against the vocabulary.

```sh
python3 -I bench.py ../../pystachy 5
```

Generated inputs and executables go to `build/suggest/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/suggest/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
