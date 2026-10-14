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

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. A 20,000-word vocabulary with 25- and 100-line texts; median wall time of five
process runs, including startup; peak RSS of one run.

| text | unknown words | CPython 3.13.16 | Pystachy AOT | speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|---:|
| 25 lines | 17 | 0.425 s | 0.119 s | 3.6x | 13.7 MB | 40.2 MB |
| 100 lines | 72 | 1.686 s | 0.331 s | 5.1x | 13.7 MB | 41.1 MB |

The baseline end-to-end speedup is 3.6–5.1×. Matching dominates as the number
of unknown words grows; the executable uses about 3× peak memory.

## Checks and reproduction

`tests/example_suggest.py` compares tokenization, generated vocabularies/text,
small cases, options and errors with CPython.

```sh
python3 -I bench.py ../../pystachy 5
```

The benchmark writes generated inputs and executables to `build/suggest/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
