# snowballstemmer 3.1.1: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `snowballstemmer-3.1.1.tar.gz`. License: BSD-3-Clause; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `e07bbc54a0d798fe6010a12398422e62a8bfbba95c394fd0956ef58cb4d3e260`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `b7deb373e5cfeb67267dde276350bebfc4b35221949145806090706cec3f681a` | 2 |
| `among.py` | `4b8b17bf3f97d46a1a536c288defe193147b15bd8edb01bbd3f64c57b8b5e2af` | 2 lines |
| `basestemmer.py` | `e60fd08f93826b9c428f038ace77500a68ba594d504cd64b1501a6fab2becbc1` | 26: 22 signatures, the fields, an import, 2 branches |
| `english_stemmer.py` | `350d71588d33ce8e2dd5084efa48c50cbaec90bec9ac3f7e97623fd640856dea` | 20: 15 return types, 4 groupings, 1 tuple |
| `porter_stemmer.py` | `b7e27d0486805a9ce69be3362dc3f995b988c4d607de438df189c21e4482b8b0` | 17: 12 return types, 2 groupings, 3 tuples |

## Adaptation record

- The generated stemmers retain upstream's `BaseStemmer` inheritance. The typed base body is shared, with no copy in either subclass.
- Methods and fields receive types; groupings and variable-index replacement tables become lists.
- `Among` method callbacks and the class-valued language factory are removed; only the two English modules are imported.
- List groupings retain exact membership semantics. The rejected faster string-grouping experiment and its timing remain in the benchmark snapshot.

<a id="the-flattening"></a>

### Restored inheritance

The initial port flattened `BaseStemmer` into each generated class because ordinary
inheritance was unsupported. The hierarchy now matches upstream: `EnglishStemmer` and
`PorterStemmer` derive from `BaseStemmer`. Removing the two copied bodies deletes 568 lines
and 56 duplicated or flattening-related `Pystachy port:` markers. The remaining source has
67 markers.

Inherited `stemWord()` calls the concrete subclass's `_stem()`; `stemWords()` uses the same
path. The inherited constructor and cursor operations share the base fields. The existing
adaptations to annotations, list groupings, replacement tables and callback scope remain.
The differential program's CPython output is identical before and after this restoration.

When refreshing the generated modules, retain their base class, annotate their return types,
and adapt the groupings and variable-index replacement tables as above. No base-body copy
is needed.

## Validation snapshot

`tests/port_snowballstemmer_stem.py` stems 384 English words, chosen for the suffixes each step
of the two algorithms removes or rewrites, and holds each one's Porter2 and Porter stems (as the
upstream package stems them under CPython): it prints any word that stems otherwise, and then
the stems of the edge cases the evaluation and its verifier tried: the empty word and short
words, apostrophes, `y` and `Y`, Porter2's exception lists and the prefixes it gives a region of
their own, capitals, digits and spaces, a word of 3,003 letters, `stemWords` of `[]` and `[""]`,
the cursor API (`set_current`, `slice_to`, `slice_from`, `insert`, `copy_from`), six non-ASCII
words that stem as in CPython, and 300 pseudo-random words; and `tests/run.sh` compares what it
prints with CPython's, JIT and AOT. It leaves out the names `algorithms()` returns (36
upstream: it prints whether `english` and `porter` are among them) and the non-ASCII words of
the non-ASCII deviations described in the port guide. Run under CPython against the unmodified upstream package, it prints
exactly what it prints against this port. The evaluation's and its verifier's longer drivers,
run against this port, print what CPython prints against the upstream package too: 106 words
(21 of them not in the test), a word of 30,003 letters and 30,000 pseudo-random words. So do
a review's 61,162 distinct tokens of letters and apostrophes, in any case, from the English
text on its machine (docstrings, comments and documentation), and 114,529 words: every word of
up to four of 17 characters (letters, `Y` and the apostrophe), and every word of up to two
followed by one of 84 suffixes. Changed one at a time, in its string or in its result (366
changes), every `Among` entry of the two stemmers whose change alters the stem of one of the
34,382 lower-case words among those tokens also changes what the test prints, except the `bl`
entries and Porter2's `ical` result, which only made-up words reach.

The test runs in 0.42 s JIT, and its AOT build takes 2.7 s (the executable then runs in
0.01 s). Collecting at every allocation (`PYSTACHY_GC_STRESS_PROGRAM=1`, compiled with
`PYSTACHY_GC_STRESS=1000`), it runs in 1.0 s JIT and in 3.3 s AOT, build included. These are
wall-clock medians of 3, taken while other jobs kept this 4-core VM's load average between 5
and 7, so they are upper bounds.

## Benchmark snapshot

The evaluation's workload: 1,000 words (40 roots with 25 suffixes each) stemmed 200 times by
both stemmers, 400,000 stems, which prints a checksum and the first 12 stems (CPython prints the
same). Built AOT against this port it takes 0.53 s, and CPython 3.13 takes 6.84 s on the
unmodified upstream package: 12.9 times as long. These are wall-clock medians of 5 on this
4-core x86-64 VM at a load average between 2 and 3, where each run's user and system CPU time
came within 0.03 s of its wall-clock time. With the rejected string-grouping alternative it
takes 0.40 s (17.2 times); the evaluation measured 0.426 s for them, against 6.565 s for
CPython (15.4 times). So the list groupings cost about a third more than strings would. For
these groupings, all ASCII letters, strings would stem exactly as lists do; lists keep the
grouping adaptation one rule that is exact for every language's groupings.
`snowballstemmer.stemmer()` returns PyStemmer's stemmers, a C extension, when that is installed;
it is not installed here (`import Stemmer` fails), and the workload makes the pure-Python classes
itself in any case.
