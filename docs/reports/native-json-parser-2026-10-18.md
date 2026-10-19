# Native JSON parser follow-up — 2026-10-18

The [first checkpoint](native-json-2026-10-18.md) found that parsing dominated the
recursive JSON record workload: 31–41 ms to parse a 5,000-record document in AOT,
against 0.7–1.0 ms to process it. This follow-up rewrites the decoder in
`lib/json.py`, extends the benchmark with PyPy, predecoded processing and text
variants, and remeasures. The compiler and runtime are unchanged. There is still
no runtime profiling or automatic specialization. Stacked on #670; refs #392 and #9,
neither of which this closes.

A review of the first version of this report (at `848e2e2`) found a regression for
text that is not UTF-8 and gaps in the benchmark's provenance; both are fixed, and
every timing below comes from one run of the fixed revision.

## Where the parse time went

Callgrind on the #670 AOT parser (skewed profile, three parses) attributes about 80%
of the instructions to reading a non-ASCII `str` one character at a time: code-point
offset translation (`text_offset` 31%, `pys_text_get` 14%, and 5% in `text_before`,
`text_bounds` and `pys_text_slice`), comparisons of one-character strings (`eqv`
16%, `memcmp` 4%, `pys_cmpop` 3%), `in " \t\n\r"` (4%) and `ord()` (3%). Each number
also tried six literal slices (`null`, `true`, ... `-Infinity`) before its digits.

The new decoder scans `s.encode()` with integer comparisons; the
[design note](../json-prototype.md#decoder) describes it. Instructions per parse,
counted with callgrind as the difference between runs of three and one parses of
the same string (AOT; deterministic):

| Decoder | skewed UTF-8 | mixed UTF-8 | ASCII | `\u`-escaped |
|---|---:|---:|---:|---:|
| #670 (`3dbc608`) | 295.9M | 287.5M | 192.0M | 247.4M |
| bytes; `decode("utf-8", "surrogatepass")` per string | 130.5M | 132.0M | 134.2M | 132.5M |
| `decode()` unless the text holds lone surrogates | 44.2M | 53.9M | 33.3M | 56.1M |
| + 64-entry object-key cache (`848e2e2`) | 32.3M | 34.3M | 29.3M | 37.6M |
| + review fixes (committed) | 31.8M | 33.8M | 28.9M | 37.5M |

Naming the codec made the runtime normalize `"utf-8"` with string concatenation and
list searches on every call: 57% of that version's instructions in a three-parse
profile. The first parse of a string also paid ~10.1M instructions for
`s.startswith("\ufeff")`, which counted all of its code points; the BOM check now
reads the first bytes, and a single fresh 5,000-record parse fell from 52.5M to
42.4M instructions. The table's method excludes that one-time cost.

The review fixes share one scan between strings and object keys, make the key cache
at the first key, count characters for error positions instead of decoding the
whole prefix, and restore #670's handling of text that is not UTF-8. Pystachy reads
files (a documented deviation), `input()` and `sys.argv` without checking their
bytes; the first version's strict `decode()` of such a slice raised
`UnicodeDecodeError` out of `loads()`, where #670's decoder parsed the text. Such
text is now parsed again, taking each string from the `str` at character offsets.
Valid text does not take that path.

Instructions per `loads()` of small documents (AOT; callgrind, the difference
between 3,000 and 1,000 calls):

| Document | #670 | `848e2e2` | committed |
|---|---:|---:|---:|
| `1` | 3,179 | 1,103 | 287 |
| `"x"` | 1,177 | 1,203 | 383 |
| `{"a": 1}` | 6,472 | 1,886 | 1,947 |
| `[1, 2.5, null, true]` | 13,585 | 3,518 | 2,704 |
| `{"id": 7, "name": "event-7", "tags": ["a", "b"]}` | 18,305 | 4,597 | 4,653 |

`848e2e2` allocated the 64-slot key cache in every call, which made a bare string
slower to parse than with #670's decoder.

## Measurement

```sh
COMMON="--compiler ./pystachy --pypy $PYPY --records 5000 --iterations 10 \
  --samples 3 --processes 3 --warmup-ms 2000"
python3.13 tools/bench_json.py $COMMON --modes cpython pypy jit aot cpython-lib pypy-lib --texts utf8
PYSTACHY_PATH=$BASE python3.13 tools/bench_json.py $COMMON --modes jit aot --texts utf8
python3.13 tools/bench_json.py $COMMON --modes cpython pypy jit aot cpython-lib pypy-lib \
  --profiles skewed --texts ascii escaped
PYSTACHY_PATH=$BASE python3.13 tools/bench_json.py $COMMON --modes jit aot --profiles skewed --texts ascii escaped
```

`$BASE` holds `3dbc608`'s `lib/json.py` (SHA-256 `9dbd1790…`); the other runs
compiled the committed one (`cd8b17b5…`). One compiler binary (`de59f53c…`, built
at `3dbc608`; this branch changes no compiler or runtime source) served all four
runs, at clean revision `ce7efe2` on 2026-10-19. CPython 3.13.16, PyPy 7.3.23
(Python 3.11.15), LLVM 18.1.3; Linux x86-64 VM with 4 vCPUs (Intel Xeon, 2.80 GHz),
load average 0.52 at the start and about 1.0 while measuring, nothing else
running. Inputs are 446–601 kB. Each configuration ran in three processes, each
with 2 s of warmup and three samples of ten documents; tables give the median of
the process medians in ms per document, with min–max of the process medians where
shown. All 480 runs matched CPython's checksums. Raw samples:
[evidence](native-json-parser-2026-10-18.json).

These numbers replace those of the
[first version](https://github.com/den-run-ai/pystachy/blob/848e2e2ab79878d8b7341314c97236948666388f/docs/reports/native-json-parser-2026-10-18.md),
which ran on another VM: there CPython's decoder parsed the skewed input in 5.77 ms
rather than 8.34 ms. Compare times only within one run.

### Parsing

| Input | CPython (C decoder) | PyPy | AOT #670 | AOT now | JIT #670 | JIT now | CPython, `lib/json.py` | PyPy, `lib/json.py` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| skewed UTF-8 | 8.34 | 3.90 | 28.49 | 4.06 | 31.07 | 5.67 | 101.8 | 22.5 |
| mixed UTF-8 | 8.61 | 4.75 | 32.80 | 4.52 | 29.46 | 5.55 | 104.7 | 24.1 |
| changing UTF-8 | 7.75 | 4.12 | 27.82 | 4.17 | 28.29 | 5.89 | 103.0 | 26.5 |
| skewed ASCII | 5.84 | 3.33 | 20.63 | 3.14 | 22.54 | 4.42 | 97.8 | 19.3 |
| skewed `\u`-escaped | 7.91 | 8.76 | 27.04 | 4.42 | 27.66 | 6.05 | 134.6 | 33.3 |

AOT parsing is 6.1–7.3× faster than #670 and JIT 4.6–5.5×. AOT parses every
input 1.8–2.1× faster than CPython's C decoder. Against PyPy's decoder the process
ranges overlap on the four inputs without escapes (skewed UTF-8, for example,
3.87–5.15 ms in AOT and 3.72–4.60 ms in PyPy); on `\u`-escaped text AOT is twice as
fast (4.42 versus 8.76). Single samples can be much slower than their process's
others: the slowest skewed sample took 6.75 ms in AOT and 6.97 ms in PyPy.

The `lib/json.py` columns run Pystachy's parser source on the other interpreters.
After 58–92 warmup rounds PyPy's tracing JIT runs it at 19–33 ms, 5.3–7.5× slower
than Pystachy's AOT build and 3.9–5.1× faster than CPython. PyPy's own `json`
decoder is not Python code. Pystachy's JIT tier parses in 1.2–1.4× the AOT time;
#392 attributes such gaps to the JIT calling the precompiled runtime where AOT
inlines it (here, for example, each byte read); this report did not profile the JIT.

### End to end

Parsing plus processing in one loop, generic consumer:

| Input | CPython | PyPy | AOT #670 | AOT now | JIT now |
|---|---:|---:|---:|---:|---:|
| skewed UTF-8 | 11.46 | 4.49 | 28.48 | 5.08 | 5.98 |
| mixed UTF-8 | 12.23 | 5.05 | 30.66 | 5.39 | 6.33 |
| changing UTF-8 | 11.58 | 4.94 | 29.94 | 4.83 | 7.91 |
| skewed ASCII | 10.21 | 4.15 | 22.33 | 3.75 | 6.18 |
| skewed `\u`-escaped | 11.85 | 9.12 | 29.60 | 5.43 | 6.71 |

AOT is now 2.2–2.7× faster than CPython end to end. PyPy is faster on mixed UTF-8
(5.05 versus 5.39; the process ranges, 4.67–5.17 and 5.30–5.63, do not overlap);
the ranges overlap on the skewed, changing and ASCII inputs; AOT is faster on
escaped text (5.43 versus 9.12). The AOT executable grew from 124,872 to 149,504
bytes and its build from 1.60–1.90 s to 1.95–2.24 s. Across the full repeated
workload, the separate `PYSTACHY_GC=stats` probes recorded 9–13 collections taking
31–58 ms, against 24–27 collections taking 149–189 ms for #670's parser, with
similar heap peaks (43.5–44.4 MiB versus 46.0–48.1 MiB). RSS was not measured (no
GNU `time`).

### Processing a decoded document

Predecoded runs decode once outside the timed region and time only the consumer:

| Profile | CPython | PyPy | JIT | AOT generic | AOT guarded | AOT rebuild |
|---|---:|---:|---:|---:|---:|---:|
| skewed | 4.24 | 0.84 | 0.31 | 0.322 (0.284–0.541) | 0.290 (0.287–0.306) | 1.46 |
| mixed | 4.52 | 1.00 | 0.36 | 0.369 (0.343–0.372) | 0.342 (0.333–0.351) | 1.72 |
| changing | 4.42 | 0.74 | 0.32 | 0.327 (0.322–0.358) | 0.367 (0.306–0.395) | 1.58 |

CPython, PyPy and JIT columns are the generic consumer. Generic AOT processing takes
0.32–0.37 ms, 2.3–2.7× less than PyPy's traces, and the JIT's takes about as long
(0.31–0.36 ms). After parsing in the same process, AOT processing is 6–9% of
parsing plus processing. The source-written guard's ranges overlap the generic
ones in all three profiles, in AOT and in the JIT. The first version of this
report found the guard faster in the JIT tier on skewed data and slower on mixed
data; this run does not reproduce that. PyPy, which specializes on the types it
observes, takes 0.74–1.00 ms; its one pair of ranges that does not overlap is the
predecoded mixed profile, where the guarded consumer is faster (0.60–0.77 versus
0.96–1.10 ms), and the same pair overlaps after parsing. CPython's processing is
noisy (3.8–8.9 ms).

Processing #670's decoded documents took 0.58–0.68 ms in AOT. The new decoder's
output is faster to process although the consumer and its instructions are the same:
in identical runs of the consumer, callgrind counts 97.7M versus 97.1M instructions
inside `process()`, while simulated L1 data-read misses fall from 3.40M to 2.39M.
Without the key cache the byte scanner already reaches 2.73M misses. The old decoder
allocated one-character strings and literal slices between the values it kept;
fewer temporaries leave the decoded graph denser.

## Would a binary JSON format help?

Not for evaluating specialization: predecoded runs already remove parsing from the
timed region and process the same mutable value graph that `loads()` returns. For
parsing, `rebuild()` copies the decoded lists and dicts, iterating their items,
around the same scalars and strings. Any decoder that produces these native values,
including one for a binary format, at least allocates and fills those containers,
and it also creates the strings and scalar boxes that `rebuild()` reuses. AOT
rebuilds take 1.46–1.72 ms, 36–38% of the UTF-8 and escaped parses (50% for ASCII
text). Another format could therefore at best bring the AOT parse to about 1.5–1.7
ms, 2.6–2.8× faster (2.0× for ASCII text), and less in practice; it could not
remove the allocation that now dominates, and it would need its own codec,
producers and correctness tests. In CPython and PyPy `rebuild()` runs as Python
code (7.9–11.9 ms), so it does not bound their native decoders.

## Skewed-type specialization

The evidence does not meet [#392](https://github.com/den-run-ai/pystachy/issues/392)'s
bar for reopening runtime skewed-type specialization: an optimization that ordinary
AOT cannot economically obtain. Generic AOT processing is already faster than PyPy's
type-specialized traces and is less than a tenth of parsing plus processing; the
guard control is inconclusive in AOT and in the JIT. The large gains in this
workload came from ordinary decoder work.

## Validation

Revision `ce7efe2`, plus this report and documentation; the measured `lib/json.py`
is the committed one. The compiler and runtime sources equal #670's, whose
bootstrap reached its fixed points locally (624,400 compiler and 18,388 runtime IR
lines).

- `python3.13 tools/json_check.py --compiler ./pystachy --native --gc-stress`:
  22,449 hosted checks, and 14,444 cases in each of JIT and AOT collecting at every
  allocation. #670's checker (`3dbc608`) also passes: 19,022 hosted checks.
- Seven parser mutations: `json_check.py` fails on four (error positions in bytes,
  a key cache without its length check, no surrogate-pair joining, characters
  counted as bytes), and the JSON fixtures on those and two more (UTF-8 sequences
  not checked, no second parse of text that is not UTF-8), which only
  `tests/deviations/json_invalid_utf8.py` catches. Disabling the lone-surrogate
  decoding is no longer observable: the second parse then decodes such text
  correctly, more slowly.
- `tests/deviations/json_invalid_utf8.py` (CPython raises `UnicodeDecodeError`
  reading its file) passes in JIT/AOT, with collection at every allocation and with
  the hosted compiler; it fails with `848e2e2`'s parser.
- `tests/json_scanner.py` (recorded with CPython 3.13.16) passes in JIT/AOT, with
  optimizations off, with collection at every allocation and with the hosted
  compiler, on both the new and #670's parser; both position mutations fail it.
- Focused JSON, recursive-alias, deviation and optional-import cases (35 files, 47
  passes per mode) pass normally, with optimizations off, with GC stress and with
  the hosted compiler.
- `make check-recordings PY=python3.13`: 1,242 recordings, 78 deviations and 9
  library copies, 0 failed.
- `tools/test_bench_json.py`: 6 pass, now also in CI's lint workflow. A `--smoke`
  run of all six modes matched CPython (72 runs), and the no-argument consumer
  prints CPython's checksum (256384) on PyPy, JIT and AOT.
- CI on `ce7efe2`: all 31 checks pass, including every verify shard, lint, the
  installs and the wheels; the DCO check for fork pull requests is skipped.

## Limits and next steps

- One shared VM, three processes per configuration. Single samples can be much
  slower than their neighbours, and some PyPy and CPython ranges are wide.
  Instruction counts carry the before/after claim; wall-clock comparisons with
  CPython and PyPy are approximate, and absolute times differ between VMs.
- Remaining AOT parse costs are allocation (strings, union boxes, containers, GC),
  string decoding and dictionary insertion.
- Runtime changes outside this library-only follow-up would help every program
  that reads text this way. The UTF-8 decoder validates each slice and copies
  non-ASCII results through a list and `join`. `str.encode()` checks and copies
  text holding any character from U+D000 to U+D7FF: a 414 kB, 5,000-record document
  of Hangul syllables from U+D000 takes 38.8M instructions per parse, against 25.8M
  for the same document at U+B000 (the difference is all `pys_str_encode`), and
  3.8–4.0 ms against 2.7–2.9 ms (best of seven samples; #670's parser takes
  16.7–17.8 ms on either). `str.startswith()` counts every code point even for a
  prefix test, and `decode("utf-8")` normalizes the codec name in every call.
- Text that is not UTF-8 is parsed twice. `\u`-escaped strings still build a chunk
  list and one-character strings per escape.
- Serialization (`dumps`) was not measured or changed.
