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
checksum and had the length of CPython's text: 655,650 characters for UTF-8, where
`ensure_ascii` escapes the non-ASCII characters of names and tags, and 500,650 for ASCII.
The [evidence](native-json-encoder-2026-10-19.json) holds every sample.

| Mode | UTF-8 before | UTF-8 after | ASCII before | ASCII after |
|---|---:|---:|---:|---:|
| AOT | 31.73 (31.68–31.88) | 7.86 (7.72–11.40) | 26.81 (25.14–28.28) | 7.31 (4.90–7.74) |
| JIT | 31.36 (30.92–36.03) | 8.26 (7.96–9.19) | 28.93 (26.14–33.08) | 5.43 (5.08–5.94) |
| CPython running `lib/json.py` | 93.04 | 89.36 | 87.74 | 47.14 |
| PyPy running `lib/json.py` | 34.12 | 31.13 | 31.04 | 19.37 |
| CPython's `json` | 7.08 | 5.14 | 4.92 | 4.68 |
| PyPy's `json` | 10.66 | 10.42 | 10.02 | 9.29 |

The last two rows run each interpreter's own `json` in both runs, so their differences
are the shared host's noise; so is the spread of AOT's ASCII samples. AOT and the JIT
encode 3.7–5.3 times faster than before, at 1.2–1.6 times the time of CPython's C encoder.
Instruction counts are steadier: callgrind counts 223.3M instructions before and 47.0M
after (4.75 times fewer) for one AOT `dumps()` of the UTF-8 document, and 189.4M and 34.9M
(5.43 times fewer) for the ASCII one. Each is the count of a program that decodes the
document and encodes it once, less that of the same program without the `dumps()` call.

A separate script timed larger documents and the other string paths: 20,000 records of
`{"id": i, "name": PREFIX + str(i) + SUFFIX, "tags": ["alpha", "beta", "gamma"],
"score": i * 0.5}`, 2.1–3.4 MB of output, with the prefixes and suffixes below. Each cell
is the median of three interleaved rounds, each the median of seven `dumps()` calls in
one process pinned to one core; every output matched CPython's byte for byte.

| Names | AOT before | AOT after | JIT before | JIT after | CPython | PyPy |
|---|---:|---:|---:|---:|---:|---:|
| ASCII: `"customer-"`, `" lorem ipsum dolor sit amet"` | 162.6 | 27.7 | 146.2 | 25.4 | 20.4 | 44.2 |
| non-ASCII: `"Grüße-"`, `" 日本語のテキスト 😀 café"` | 162.6 | 51.8 | 165.9 | 61.3 | 23.6 | 39.0 |
| the same, `ensure_ascii=False` | 122.4 | 26.7 | 133.9 | 20.9 | 32.7 | 42.2 |
| escapes: `"line\n\"quoted\"-"`, `"\ttab\\back\r end"` | 135.3 | 28.2 | 141.1 | 25.7 | 23.9 | 34.6 |

That takes `dumps()` from 3.7–8 times CPython's time to 0.6–2.6 times it. Non-ASCII text
that `ensure_ascii=True` escapes stays the slowest case, at 2.2–2.6 times CPython's.

## Where the time goes now

Of the 47.0M instructions that encode the UTF-8 document, about 17M join the output's
pieces and copy them (`pys_str_join` and `memcpy`), 8M scan string bytes in `_quote()`,
4.6M are `_Encoder.write()`'s own, about 3M format floats, 2.5M are `str.encode()`'s, and
3.7M decode and escape non-ASCII characters (`_u8len()` and `_escape()`). None of these
dominates; fewer, larger pieces would trade the join's work for new strings.

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
- `tools/test_bench_json.py` checks that a sample whose text has another length than
  CPython's, or a run without that reference, is rejected.
