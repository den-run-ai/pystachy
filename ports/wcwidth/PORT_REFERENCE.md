# wcwidth 0.9.2: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `wcwidth-0.9.2.tar.gz`. License: MIT with Markus Kuhn notice; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `ae0ef90b90f6af38b54f1fe6d58662ec33b3cb4b8391958a62416d654231727b`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `646c6b7a3dc93d36475da57f1da58b83879ca323f97c8d7b0345614de51ad9cc` | 12 regions: imports, `os.environ`, the C extension's branch, `__all__` |
| `_wcwidth.py` | `d90e01620d4bacb231cc15584cd20c36f36bd1084894d93c5e26eec06fc0e688` | 1 region: legacy variable-length-tuple helper's cache |
| `_wcswidth.py` | `674f1420fce6114b02b7e371fc574c4553776efa5b7b0982df5fcaef93e40b4e` | 9 regions |
| `_constants.py` | `04425f05bce4197bac837bbb40c07e10e070da21fc1dd39c28be0f6052425a68` | 11 regions |
| `bisearch.py` | `63f15dbd84f31570f6a5ae5ca6951e803e525dfcbe07c1c2e00f6bac939d6f8d` | 1 line |
| `unicode_versions.py` | `0504f550c0e77dd1b3c81c408a0d7c1888cfae2ee319aac5c45e755040439bb0` | 1 line |
| `table_grapheme.py` | `3176cee3c7c78311592287cd5a44509d48199d98bdf46731058c66974df0ed6d` | 3 regions: 16 of its 20 tables left out |
| `table_zero.py` | `03d61051c69f286fe77acca5583be371fa674f86cff61a6abdc57fa1a5156cc6` | none |
| `table_wide.py` | `a167dfa17738fb939b8157193fc9d11f70b1e1ed0385e1a6faee07c8d5ad5085` | none |
| `table_ambiguous.py` | `762d8dfbdd8ad6a71bf50015e89d4dd4dbc5b3d270560e1c3c90130fda98657d` | none |
| `table_mc.py` | `f084236a9b43821968521672ec34c79c336f224c352c17b0eb82afbfcdb1fa61` | none |
| `table_vs15.py` | `9af55c5c6801b678a4c110126f8032309ac8610640b1ca74be4ea0a3585e478b` | none |
| `table_vs16.py` | `16371e2db996fd6e60ac63905f9d9e8323429b71742c765b83a4a5d7519ab0c6` | none |

## Adaptation record

- Binary-search tables become lists; the grapheme file keeps the four tables used by the two exposed functions.
- C-extension/per-terminal branches are omitted; dictionary membership replaces frozenset code-point membership.
- Upstream's `wcwidth` and `_wcmatch_version` cache decorators are retained. Only the cache
  on the unsupported `_wcversion_value` variable-length-tuple helper is omitted.
- `_split_chars()` decodes UTF-8 sequences and bounds work by `n=`; the CPython branch preserves character-based input during differential recording.
- The adapted parameter checks use static integer types, and the ASCII fast path spells out printable-character bounds.

## Validation snapshot

`tests/port_wcwidth_core.py` runs the cases of wcwidth's own test suite for the two functions
(`tests/test_core.py`, `test_emojis.py`, `test_ambiguous.py` and `test_ucslevel.py` of the sdist,
run under pytest there) as a program: for each phrase, the width of each character and of the
phrase. They cover CJK and Katakana, NUL and ESC, combining marks, Balinese, Devanagari, Tamil,
Kannada, Bengali, Javanese, Burmese and Khmer conjuncts, Hangul jamo, ZWJ emoji sequences, flags
of 1 to 4 regional indicators, skin tones, VS16, the prepended concatenation marks, ambiguous
characters at both widths, `ambiguous_width` clamped, `n=` and the ignored `unicode_version`.
`tests/port_wcwidth_edges.py` takes the edge cases the port met: `wcwidth()` at both ends of every
range of the zero-width, wide and ambiguous tables and one past them (2,587 code points), and at
every 37th code point up to 0x10FFFF, surrogates included, at both ambiguous widths (histograms
and a checksum); every C0 and C1 control, alone, and some in text; text whose UTF-8 has the bytes
0x80-0x9F, which `wcswidth()` took for controls before the edit; grapheme clusters (VS15 and VS16
without a base, odd and even runs of regional indicators, a tag sequence, ZWJ after a non-emoji,
Thai); `n=` at and around the boundaries of a ZWJ family, past the end, negative and 2**63 - 1;
`ambiguous_width` from -(2**63 - 1) to 2**63 - 1; 1,001 characters of text; `wcwidth()` of two
characters, which raises `TypeError`; text of `chr()` bytes below 256, alone and around other
characters, among them bytes that start no well-formed UTF-8 sequence (cut short, overlong, above
0x10FFFF), where the split by lead byte alone raised `TypeError`; and the names that
`from wcwidth import *` binds.

`tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under CPython against the
unmodified upstream package (where the C extension is not built), both print exactly what they
print against this port. Both pass JIT and AOT with the native compiler and the CPython-hosted
one, and with `PYSTACHY_OPT=-all`, and `tests/run.sh` passes as a whole (1,935 passed, 0 failed).
They stay small under `make verify`'s gc-stress stage (the compiler collecting every 1,000
allocations, the program at every allocation): the JIT run and the AOT build and run of
`port_wcwidth_core` take 4.9 s of CPU together (0.8 s JIT, 4.0 s build, 0.04 s run), and those of
`port_wcwidth_edges` 6.9 s (1.7 s, 4.2 s, 1.0 s), about as long in wall clock on a 4-core VM at
load 5 to 8. Without gc-stress, each JIT run takes 0.4 s of CPU.

## Benchmark snapshot

**Run time.** The headline workload: 160,000 `wcswidth()` calls, at both ambiguous widths, on four
lines of mixed text (CJK, a ZWJ family, a heart with VS16, a flag, a skin tone, Katakana,
fullwidth Latin, a Devanagari conjunct, Thai, ambiguous characters, Cyrillic, Hebrew, accented
Latin), then `wcwidth()` of each code point from 0x100 to 0x2FFFF (checksum `5320000 312269` in
both). Median of 3 runs, wall clock with process start-up and CPU time, on a 4-core x86-64 VM that
was running other jobs (load 7 to 8):

| | wall clock | CPU |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.148 s | 0.148 s |
| CPython 3.13.16, unmodified wcwidth 0.9.2, pure Python | 1.522 s | 1.506 s |

That is 10.3 times faster in wall clock and 10.2 times in CPU time; a second set gave 10.0 and
10.1. About 0.02 s of the AOT time is `_split_chars()` checking that the bytes of each character
are well formed: splitting by the lead byte alone, which raised `TypeError` on other bytes, took
0.123 s of CPU. CPython runs upstream's Python code here, `lru_cache` on `wcwidth()` included. But
wcwidth also has a C extension, `wcwidth._wcwidth_c` (`libwcwidth/`): PyPI has wheels with it
(`abi3` for CPython 3.10 and later, and free-threaded 3.14t and 3.15t ones, for Linux, macOS and
Windows) besides a pure-Python `py3-none-any` one, and its `setup.py` compiles it, when it can, in
an install from the sdist, so a typical CPython install runs C for both functions. The runs above
import the sdist's source tree, where it is not built (`HAS_C_EXTENSION` is `False`); this does not
compare the C extension, which would mean running a downloaded binary wheel or the sdist's
`setup.py`.

**Build time.** `pystachy build` of a program that imports `wcwidth` and calls `wcwidth()` once
takes 3.2 s of CPU (3.2 s of wall clock, at load 5 to 6), against 0.15 s for `print(1)`;
`tests/port_wcwidth_core.py` takes 3.6 s and `tests/port_wcwidth_edges.py` 3.7 s (medians of 3,
wall clock about the same; 4.0 and 4.2 s of CPU with the compiler collecting every 1,000
allocations). Of the 20,000 lines of LLVM IR of a test, 10,200 build the port's tables (1,245
ranges) at import, and 5,700 are `_constants.py`'s import, where `list()` of a tuple and a `for`
over one copy the tuple's items with one call each (1,040 calls). With `table_grapheme.py` as
upstream ships it (3,283 ranges in all), the program above and `port_wcwidth_edges` take 5.8 s and
6.2 s of CPU to build. `pystachy ir` alone takes 0.1 s of CPU.
