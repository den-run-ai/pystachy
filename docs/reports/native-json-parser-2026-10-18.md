# Native JSON parser follow-up — 2026-10-18

The [first checkpoint](native-json-2026-10-18.md) found that parsing dominated the
recursive JSON record workload: 31–41 ms to parse a 5,000-record document in AOT,
against 0.7–1.0 ms to process it. This follow-up rewrites the decoder in
`lib/json.py`, extends the benchmark with PyPy, predecoded processing and text
variants, and remeasures. The compiler and runtime are unchanged. There is still
no runtime profiling or automatic specialization. Stacked on #670; refs #392 and #9,
neither of which this closes.

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
| + 64-entry object-key cache (committed) | 32.3M | 34.3M | 29.3M | 37.6M |

Naming the codec made the runtime normalize `"utf-8"` with string concatenation and
list searches on every call: 57% of that version's instructions in a three-parse
profile. The first parse of a string also paid ~10.1M instructions for
`s.startswith("\ufeff")`, which counted all of its code points; the BOM check now
reads the first bytes, and a single fresh 5,000-record parse fell from 52.5M to
42.4M instructions. The table's method excludes that one-time cost.

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
compiled the committed one (`c88cf3ce…`). One compiler binary (`de59f53c…`, built
at `3dbc608`; this branch changes no compiler or runtime source) served all four
runs, at clean revisions `a110c14` and `258c9a5` (documentation-only difference).
CPython 3.13.16, PyPy 7.3.23 (Python 3.11.15), LLVM 18.1.3; Linux x86-64 VM with
4 vCPUs, load average 0.15 at the start and about 1.0 while measuring, nothing else
running. Inputs are 446–601 kB. Each configuration ran in three processes, each
with 2 s of warmup and three samples of ten documents; tables give the median of
the process medians in ms per document, with min–max of the process medians where
shown. All 480 runs matched CPython's checksums. Raw samples:
[evidence](native-json-parser-2026-10-18.json).

### Parsing

| Input | CPython (C decoder) | PyPy | AOT #670 | AOT now | JIT #670 | JIT now | CPython, `lib/json.py` | PyPy, `lib/json.py` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| skewed UTF-8 | 5.77 | 2.60 | 26.52 | 3.50 | 30.69 | 7.02 | 107.8 | 54.4 |
| mixed UTF-8 | 7.01 | 4.81 | 26.71 | 3.55 | 27.95 | 6.22 | 108.9 | 56.6 |
| changing UTF-8 | 6.84 | 2.96 | 26.60 | 3.19 | 28.86 | 5.57 | 102.0 | 54.4 |
| skewed ASCII | 4.42 | 1.99 | 20.38 | 2.38 | 21.71 | 4.81 | 93.7 | 45.1 |
| skewed `\u`-escaped | 6.44 | 5.53 | 29.14 | 3.46 | 29.13 | 8.87 | 130.6 | 67.7 |

AOT parsing is 7.5–8.6× faster than #670 and JIT 3.3–5.2×. AOT now parses every
input faster than CPython's C decoder (1.6–2.1×). PyPy's decoder remains faster on
three inputs (skewed 2.60 versus 3.50, changing 2.96 versus 3.19, ASCII 1.99 versus
2.38) and slower on escaped text. Its mixed-profile median of 4.81 is noisy: its
guarded-label runs, which parse identically, gave 2.93 (range 2.68–4.01). Pystachy's
samples are bimodal on this host: the skewed AOT process medians range 3.29–5.66 ms,
and individual samples alternate between about 3.3 and 5–6 ms.

The `lib/json.py` columns run Pystachy's parser source on the other interpreters.
After ~70 warmup rounds PyPy's tracing JIT runs it at 45–68 ms, 15–20× slower than
Pystachy's AOT build and about twice CPython's speed. PyPy's own `json` decoder is
not Python code. The JIT tier parses at about twice the AOT time, consistent with
#392's observation that the JIT calls the precompiled runtime where AOT inlines it
(here, for example, each byte read); this report did not profile the JIT.

### End to end

Parsing plus processing in one loop, generic consumer:

| Input | CPython | PyPy | AOT #670 | AOT now | JIT now |
|---|---:|---:|---:|---:|---:|
| skewed UTF-8 | 8.98 | 3.27 | 25.37 | 5.64 (3.89–5.97) | 7.62 |
| mixed UTF-8 | 10.05 | 4.84 | 27.74 | 4.40 | 6.48 |
| changing UTF-8 | 11.13 | 3.58 | 29.48 | 3.91 | 5.68 |
| skewed ASCII | 8.32 | 3.05 | 25.73 | 2.97 | 4.63 |
| skewed `\u`-escaped | 9.72 | 7.30 | 27.87 | 4.78 | 8.36 |

AOT is now 1.6–2.8× faster than CPython end to end (skewed's median falls on the
slow mode of its bimodal samples). PyPy is faster on skewed UTF-8 (3.27 versus 5.64;
the process ranges, 3.16–3.86 and 3.89–5.97, do not overlap); the ranges overlap on
the mixed, changing and ASCII inputs; AOT is faster on escaped text (4.78 versus
7.30). The AOT executable grew from 129,000 to 149,032 bytes and its build from
1.53–1.55 s to 1.88–1.99 s. Across the full repeated workload, the separate
`PYSTACHY_GC=stats` probes recorded 9–13 collections taking 17–50 ms, against 24–27
collections taking 138–171 ms for #670's parser, with similar heap peaks (43.5–44.4
MiB versus 46.0–48.1 MiB). RSS was not measured (no GNU `time`).

### Processing a decoded document

Predecoded runs decode once outside the timed region and time only the consumer:

| Profile | CPython | PyPy | JIT | AOT generic | AOT guarded | AOT rebuild |
|---|---:|---:|---:|---:|---:|---:|
| skewed | 3.40 | 0.59 | 0.43 | 0.245 (0.237–0.381) | 0.283 (0.253–0.392) | 1.23 |
| mixed | 6.56 | 0.61 | 0.29 | 0.370 (0.277–0.643) | 0.280 (0.268–0.349) | 1.45 |
| changing | 3.77 | 0.60 | 0.46 | 0.255 (0.253–0.291) | 0.273 (0.258–0.395) | 1.27 |

CPython, PyPy and JIT columns are the generic consumer. Generic AOT processing takes
0.25–0.37 ms, 1.6–2.4× less than PyPy's traces; after parsing in the same process it
is 8–10% of AOT parsing plus processing. The source-written guard's AOT ranges
overlap the generic ones in all three profiles. In the JIT tier the guard is faster
on skewed data (0.271–0.352 versus 0.413–0.432) and slower on mixed data
(0.304–0.340 versus 0.276–0.285), plausibly because its generic operations are
runtime calls there. PyPy, which specializes on the types it observes, shows no
difference between profiles or algorithms beyond noise (0.58–0.82 ms). CPython's
processing is noisy (3.0–6.9 ms).

Processing #670's decoded documents took 0.46–0.56 ms in AOT. The new decoder's
output is faster to process although the consumer and its instructions are the same:
in identical runs of the consumer, callgrind counts 97.7M versus 97.1M instructions
inside `process()`, while simulated L1 data-read misses fall from 3.39M to 2.39M.
Without the key cache the byte scanner already reaches 2.73M misses and 0.29 ms
(0.26 ms with it, 0.50 ms for #670 in an interleaved rerun). The old decoder
allocated one-character strings and literal slices between the values it kept; fewer
temporaries leave the decoded graph denser.

## Would a binary JSON format help?

Not for evaluating specialization: predecoded runs already remove parsing from the
timed region and process the same mutable value graph that `loads()` returns. For
parsing, `rebuild()` copies the decoded lists and dicts around the same scalars
and strings. Any decoder that produces these native values, including one for a
binary format, at least allocates and fills those containers, and it also creates
the strings and scalar boxes that `rebuild()` reuses. AOT rebuilds take 1.23–1.45
ms, 35–41% of the UTF-8 parse (54% for ASCII text). Another format could
therefore at best bring the AOT parse to about 1.2–1.5 ms, 2.4–2.9× faster (1.8×
for ASCII text), and less in practice; it could not remove the allocation that now
dominates, and it would need its own codec, producers and correctness tests. In
CPython and PyPy `rebuild()` runs as Python code (4.6–13.7 ms), so it does not bound
their native decoders.

## Skewed-type specialization

The evidence does not meet [#392](https://github.com/den-run-ai/pystachy/issues/392)'s
bar for reopening runtime skewed-type specialization: an optimization that ordinary
AOT cannot economically obtain. Generic AOT processing is already faster than PyPy's
type-specialized traces and is about a tenth of parsing plus processing; the guard
control is inconclusive in AOT. The JIT result points instead at inlining the
runtime's small operations in that tier. The large gains in this workload came
from ordinary decoder work.

## Validation

Revision `258c9a5` plus this report; the measured `lib/json.py` is unchanged since.
The compiler and runtime sources equal #670's, whose bootstrap reached its fixed
points locally (624,400 compiler and 18,388 runtime IR lines).

- `python3.13 tools/json_check.py --compiler ./pystachy --native --gc-stress`:
  22,449 hosted checks, and 14,444 cases in each of JIT and AOT collecting at every
  allocation. The original 11,017-case corpus is unchanged; its 19,022-check hosted
  run also passes. Byte-offset errors, a key cache without its length check, a
  decoder without the lone-surrogate fallback and one without surrogate-pair joining
  each fail it.
- `tests/json_scanner.py` (recorded with CPython 3.13.16) passes in JIT/AOT, with
  optimizations off, with collection at every allocation and with the hosted
  compiler, on both the new and #670's parser; the byte-offset mutation fails it.
- Focused JSON, recursive-alias, deviation and optional-import cases (33 files, 43
  passes per mode) pass normally, with optimizations off, with GC stress and with
  the hosted compiler.
- `make check-recordings PY=python3.13`: 1,242 recordings, 77 deviations and 9
  library copies, 0 failed. `ruff check` and the clang warning build pass. Local
  `shellcheck` 0.10 flags SC3013 in the unchanged `tests/cache.sh`.
- Benchmark evidence tests: 5 pass. The no-argument consumer prints CPython's
  checksum (256384) on PyPy, JIT and AOT.
- Small documents: `{"a": 1}` takes 205 ns per `loads()` (#670: 697 ns); a bare
  3-character string takes 147 ns (#670: 105 ns), the cost of the key-cache lists.

## Limits and next steps

- One shared VM, three processes per configuration. Pystachy's samples are bimodal
  here; PyPy's and CPython's ranges are wide in places. Instruction counts carry the
  before/after claim; wall-clock comparisons with CPython and PyPy are approximate.
- Remaining AOT parse costs are allocation (strings, union boxes, containers, GC),
  string decoding and dictionary insertion. The runtime's UTF-8 decoder validates
  each slice and copies non-ASCII results through a list and `join`; a codec-name
  fast path for `"utf-8"` would help every program that names it; both are runtime
  changes outside this library-only follow-up.
- `\u`-escaped strings still build a chunk list and one-character strings per escape.
- Serialization (`dumps`) was not measured or changed.
