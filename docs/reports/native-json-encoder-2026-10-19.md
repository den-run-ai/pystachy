# Native JSON encoder follow-up — 2026-10-19

The review of #670 found `json.dumps()` several times slower than CPython's on large
documents: `_quote()` appended each character of each string to a list, and formatted
each `\u` escape with `format()`. This follow-up rewrites string quoting in
`lib/json.py`, as the [design note](../json-prototype.md#encoder) describes. The text
`dumps()` returns is unchanged: it matches CPython's byte for byte on every document
below. The benchmark's predecoded phase now also times `dumps()`.

## Measurement

`tools/bench_json.py` ran the predecoded phase for 5,000 skewed records, UTF-8 and ASCII
texts, in every mode: once with the committed `lib/json.py`, once with main's
(`0c8b442`) through `PYSTACHY_PATH`, with one compiler binary.

```sh
python3.13 tools/bench_json.py --compiler ./pystachy --pypy /path/to/pypy3 \
  --modes cpython pypy jit aot cpython-lib pypy-lib --phases predecoded \
  --profiles skewed --texts utf8 ascii --records 5000
```

The host was a shared 4-vCPU Linux x86-64 VM with CPython 3.13.16, PyPy 3.11 (7.3.23)
and LLVM 18.1.3. Each cell is the median, over three processes, of each process's median
sample (three samples of five documents, after two seconds of warmup), in milliseconds per
document; the range is the three processes'. Every sample's text decoded to CPython's
checksum and had the length and order-sensitive digest of CPython's text: 655,650
characters for UTF-8, where `ensure_ascii` escapes the non-ASCII characters of names and
tags, and 500,650 for ASCII.
The [evidence](native-json-encoder-2026-10-19.json) holds every sample.

| Mode | UTF-8 before | UTF-8 after | ASCII before | ASCII after |
|---|---:|---:|---:|---:|
| AOT | 30.02 (29.96–30.56) | 6.99 (6.71–7.26) | 24.42 (24.40–27.27) | 6.77 (4.84–7.01) |
| JIT | 37.37 (30.77–41.02) | 8.62 (8.32–11.19) | 34.33 (29.58–39.84) | 5.48 (5.44–6.47) |
| CPython running `lib/json.py` | 98.24 | 74.90 | 84.62 | 48.75 |
| PyPy running `lib/json.py` | 40.60 | 43.40 | 31.51 | 21.10 |
| CPython's `json` | 5.32 | 5.36 | 7.43 | 5.17 |
| PyPy's `json` | 10.27 | 9.42 | 9.23 | 10.41 |

The last two rows run each interpreter's own `json` in both runs, so their differences
are the shared host's noise; so are the spread of AOT's ASCII samples and PyPy's UTF-8
result for `lib/json.py`, whose processes ranged from 36.6 to 43.1 ms before and from 31.0
to 44.5 ms after. AOT and the JIT encode 3.6–6.3 times faster than before, at 1.1–1.6
times the time of CPython's C encoder. Instruction counts are steadier: callgrind counts
223.3M instructions before and 44.7M after (4.99 times fewer) for one AOT `dumps()` of the
UTF-8 document, and 189.4M and 34.8M (5.44 times fewer) for the ASCII one. Each is the
count of a program that decodes the document and encodes it once, less that of the same
program without the `dumps()` call.

A separate script timed larger documents and the other string paths: 20,000 records of
`{"id": i, "name": PREFIX + str(i) + SUFFIX, "tags": ["alpha", "beta", "gamma"],
"score": i * 0.5}`, 2.1–3.4 MB of output, with the prefixes and suffixes below. Each cell
is the median of three interleaved rounds, each the median of seven `dumps()` calls in
one process pinned to one core; every output matched CPython's byte for byte.

| Names | AOT before | AOT after | JIT before | JIT after | CPython | PyPy |
|---|---:|---:|---:|---:|---:|---:|
| ASCII: `"customer-"`, `" lorem ipsum dolor sit amet"` | 153.6 | 29.9 | 172.9 | 27.3 | 20.9 | 45.1 |
| non-ASCII: `"Grüße-"`, `" 日本語のテキスト 😀 café"` | 158.2 | 44.8 | 172.9 | 45.0 | 28.4 | 36.1 |
| the same, `ensure_ascii=False` | 125.4 | 24.0 | 134.0 | 21.4 | 29.1 | 42.7 |
| escapes: `"line\n\"quoted\"-"`, `"\ttab\\back\r end"` | 137.0 | 25.6 | 139.1 | 26.4 | 18.8 | 32.5 |

That takes `dumps()` from 4.3–8.3 times CPython's time to 0.7–1.6 times it. Non-ASCII text
that `ensure_ascii=True` escapes stays the slowest case, at 1.6 times CPython's.

## Where the time goes now

Of the 44.7M instructions that encode the UTF-8 document, about 17M join the output's
pieces and copy them (`pys_str_join` and `memcpy`), 6.1M scan string bytes in `_quote()`,
4.6M are `_Encoder.write()`'s own, about 4M format numbers (`snprintf`), 2.5M are
`str.encode()`'s, and 3.9M decode and escape non-ASCII characters (`_u8char()` and
`_escape()`). None of these dominates; fewer, larger pieces would trade the join's work
for new strings.

## Validation

- On CPython 3.13.16, `lib/json.py`'s `dumps()` and CPython's agree in 240,000 comparisons:
  40,000 random strings of ASCII and control characters, quotes, DEL, Latin-1, BMP and
  astral characters and lone surrogates, each alone and in a list and an object, in both
  `ensure_ascii` modes.
- `tests/json_encoder_strings.py`, recorded with CPython 3.13.16, covers each ASCII
  character alone and within text, non-ASCII characters next to escapes, long runs on
  either side of one escape, keys and lone surrogates, in both modes. It, the other JSON
  tests and the [non-UTF-8 deviation](../../tests/deviations/json_invalid_utf8.py) pass in
  JIT and AOT, normally, with a collection at every allocation and under UBSan.
- `python3.13 tools/json_check.py --compiler ./pystachy --native --gc-stress`: 22,449
  hosted checks, and 14,444 cases each in JIT and AOT with a collection at every
  allocation.
- `tools/test_bench_json.py` checks that a sample whose text has another length or digest
  than CPython's, or a run without that reference, is rejected, and that the digest tells
  apart texts of one length whose keys or characters come in another order.
