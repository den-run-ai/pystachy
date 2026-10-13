# wcwidth 0.9.2, ported to Pystachy

[wcwidth](https://pypi.org/project/wcwidth/) tells how many cells of a terminal a character or a
string takes: `wcwidth()` and `wcswidth()` are the POSIX functions of those names, for Unicode.
East Asian wide and fullwidth characters take 2 cells, combining marks and other zero-width
characters 0, and controls -1; `wcswidth()` also measures grapheme clusters as terminals draw them
(emoji joined by ZWJ, flags, the variation selectors VS15 and VS16, skin tones, virama conjuncts
and spacing marks). It is rank 118 on PyPI in October 2026. prompt_toolkit (the line editor of
IPython), prettytable, ftfy and blessed depend on it, and tabulate uses it to align columns of CJK
text when it is installed (its `widechars` extra). These are 13 of its modules from the sdist
`wcwidth-0.9.2.tar.gz` (SHA-256
`ae0ef90b90f6af38b54f1fe6d58662ec33b3cb4b8391958a62416d654231727b`), MIT licensed (`LICENSE`,
which also has the notice of Markus Kuhn's C code that wcwidth derives from).

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `646c6b7a3dc93d36475da57f1da58b83879ca323f97c8d7b0345614de51ad9cc` | 11 regions: imports, `os.environ`, the C extension's branch, `__all__` |
| `_wcwidth.py` | `d90e01620d4bacb231cc15584cd20c36f36bd1084894d93c5e26eec06fc0e688` | 1 region: `lru_cache` |
| `_wcswidth.py` | `674f1420fce6114b02b7e371fc574c4553776efa5b7b0982df5fcaef93e40b4e` | 9 regions |
| `_constants.py` | `04425f05bce4197bac837bbb40c07e10e070da21fc1dd39c28be0f6052425a68` | 10 regions |
| `bisearch.py` | `63f15dbd84f31570f6a5ae5ca6951e803e525dfcbe07c1c2e00f6bac939d6f8d` | 1 line |
| `unicode_versions.py` | `0504f550c0e77dd1b3c81c408a0d7c1888cfae2ee319aac5c45e755040439bb0` | 1 line |
| `table_grapheme.py` | `3176cee3c7c78311592287cd5a44509d48199d98bdf46731058c66974df0ed6d` | 3 regions: 16 of its 20 tables left out |
| `table_zero.py` | `03d61051c69f286fe77acca5583be371fa674f86cff61a6abdc57fa1a5156cc6` | none |
| `table_wide.py` | `a167dfa17738fb939b8157193fc9d11f70b1e1ed0385e1a6faee07c8d5ad5085` | none |
| `table_ambiguous.py` | `762d8dfbdd8ad6a71bf50015e89d4dd4dbc5b3d270560e1c3c90130fda98657d` | none |
| `table_mc.py` | `f084236a9b43821968521672ec34c79c336f224c352c17b0eb82afbfcdb1fa61` | none |
| `table_vs15.py` | `9af55c5c6801b678a4c110126f8032309ac8610640b1ca74be4ea0a3585e478b` | none |
| `table_vs16.py` | `16371e2db996fd6e60ac63905f9d9e8323429b71742c765b83a4a5d7519ab0c6` | none |

The rest of the package is left out: the modules of the API beyond `wcwidth()` and `wcswidth()`
(see below), the per-terminal tables that only `wcstwidth()` reads (`table_overrides.py`,
`table_term_programs.py`, `table_grapheme_overrides/`), the legacy module `wcwidth/wcwidth.py` and
the C extension (`_wcwidth_c.c`, `libwcwidth/`). Every edit is marked `# Pystachy port:` in the
source, 36 regions in 7 files, and `diff -ru` against the sdist's `wcwidth/` shows them all. Code
is commented out rather than deleted, but for the tables of `table_grapheme.py`.

## The edits, and the feature each one stands in for

**M1, lenient annotations and cheap refinements ([#6](https://github.com/den-run-ai/pystachy/issues/6)).**

- **Tuples indexed by a variable** (item 8). `bisearch(ucs, table)`, the binary search behind both
  functions, reads `table[mid]`. Pystachy indexes a tuple only by a constant (`tuple index must be
  an integer constant`) and has no type for a tuple of any length (`unsupported type annotation`),
  so `table` is annotated `list[tuple[int, int]]` instead of `tuple[tuple[int, int], ...]`, and
  the tables it gets are lists: `list()` of each of the four in `_constants.py` (zero width, wide,
  ambiguous, spacing marks), and of the two variation-selector tables, made once at the top of
  `_wcswidth.py` where `wcswidth()` took them from their dicts at each call.
- **Variable-length tuple types.** `list_versions() -> tuple[str, ...]` is written
  `-> tuple[str]`, the one-item tuple it returns; `_constants.py` calls it at import. The type
  alias `_RangeTuple = Tuple[Tuple[int, int], ...]` (`unsupported module attribute typing.Tuple`),
  and `_merge_ranges()`, `TerminalOverrides` and `_EMPTY_OVERRIDES`, whose types are made of it
  (`unsupported type annotation`), are commented out, with the import of `table_overrides.py`,
  whose dicts are annotated with such tuples. They serve only `get_term_overrides()`, for
  `wcstwidth()`. Item 1 treats such annotations as absent.
- **A flag of the module** (item 4). `__init__.py` imports either the C extension's functions or
  the Python ones, on `HAS_C_EXTENSION`. Pystachy compiles both branches, and the first imports
  `wcwidth._wcwidth_c`, which is not there; only the `else` branch is kept, as
  `if not HAS_C_EXTENSION:`. The `try: import wcwidth._wcwidth_c ... except ImportError` that sets
  the flag compiles as it is, and leaves it `False`.
- **Reading `os.environ`** (item 7). `os.environ.get('WCWIDTH_PYTHON', '')`, which skips the C
  extension when set, is `os.getenv('WCWIDTH_PYTHON', '')` (`unsupported call
  os.environ.get(str,str)`).

**M3, functions as values ([#8](https://github.com/den-run-ai/pystachy/issues/8)).**

- Of the five `@lru_cache` decorators, those of `wcwidth()` and `_wcmatch_version()` are
  upstream's, with the imports of `functools` ([`lib/functools`](../../lib/README.md#functools-pystachys-own)).
  The other three are commented out, for the types of their functions: `_wcversion_value()`
  returns a `tuple[int, ...]` (M1), and `_constants.py`'s `get_term_overrides()` returns a
  `TerminalOverrides`, left out with its tuple types (M1), and `resolve_terminal()` takes a
  `bool | str` (M4). The caches only save time: calls return what they returned.
- `wcswidth()` chose `_wcwidth = wcwidth if ambiguous_width == 1 else lambda c: wcwidth(c, 'auto',
  ambiguous_width)` and called `_wcwidth(char)`; its loop calls `wcwidth(char, 'auto',
  ambiguous_width)`, which both choices call.
- `wcswidth()` bound `_bisearch = bisearch` as a local (`function 'bisearch' cannot be used as a
  value`); `_wcswidth.py` imports it as `from .bisearch import bisearch as _bisearch` instead, so
  the calls are unchanged.

**M4, dynamic values ([#9](https://github.com/den-run-ai/pystachy/issues/9)), and the native
stdlib hubs ([#11](https://github.com/den-run-ai/pystachy/issues/11)).** `_wcswidth.py` does not
import `table_grapheme_overrides`, which loads one module per terminal with
`importlib.import_module` and `getattr()`; only `wcstwidth()` reads it. `__init__.py` does not
import the modules of the rest of the API, which need `re`, `enum`, `textwrap` and `itertools`
(below), nor the legacy module `wcwidth/wcwidth.py`, which imports them all. Its `__all__`
names only what it imports, `wcwidth`, `wcswidth`, `wcstwidth`, `list_versions` and
`list_term_programs`, so that `from wcwidth import *` compiles: with upstream's 21 names, it
looked for the missing `width` as a module (`module 'wcwidth.width' is not supported`).

**M7, the long tail ([#12](https://github.com/den-run-ai/pystachy/issues/12)).**

- **Sets.** `_REGIONAL_INDICATOR_SET`, `_ISC_VIRAMA_SET` (built by a generator with two `for`
  clauses over a starred tuple display, `(*ISC_VIRAMA, *ISC_INVISIBLE_STACKER)`) and
  `_EMOJI_ZWJ_SET` (a union) are frozensets of code points. They are `dict[int, bool]`s that map
  each code point to `True`, filled by loops, and `ucs in d` tests them as `ucs in s` did (26, 41
  and 2,856 code points). `table_term_programs.py`, whose `KNOWN_TERMINALS` is a frozenset
  display, is not imported; only `list_term_programs()` and `resolve_terminal()` read it.
- **`str.isprintable()`** is missing (`'str' has no method 'isprintable'`). `wcswidth()`'s fast
  path for printable ASCII tests `pwcs.isascii() and all(' ' <= c <= '~' for c in pwcs)`, which is
  the same test on ASCII.

**Outside the roadmap: indexing a `str` gives bytes.** Pystachy's `str` holds UTF-8, and `len()`
and indexing count bytes ([docs/language.md](../../docs/language.md#deviations-from-cpython)).
`wcswidth()` walks its text by index, `pwcs[idx]`, and measured each byte as a character: no
error, but wrong widths, since the bytes 0x80-0x9F of a UTF-8 sequence have the values of the C1
controls. Before this edit `wcswidth("é")` was 2 (CPython: 1), `wcswidth("café")` 5 (4) and
`wcswidth("Ред")` 6 (3), while `wcswidth("中文")`, `wcswidth("€")`, `wcswidth("😀")` and
`wcswidth("❤️")` were -1. `_split_chars()`, added to `_wcswidth.py`, returns the characters of a
`str` as `ord()` reads them (runtime.c's `u8char()`): a well-formed UTF-8 sequence is one
character, whose `ord()` is its code point, and any other byte is one, whose `ord()` is its value.
Such bytes come from `chr()` below 256, which is one byte in Pystachy, and from text cut inside a
character; splitting by the lead byte alone took the bytes after them into one item, and `ord()`
of that raised `TypeError` (`wcswidth(chr(0xE9) + "ab")`: CPython 3). `wcswidth()` reads that list
where it read `pwcs`: `_chars[idx]` for `pwcs[idx]`, twice, and `len(_chars)` for `len(pwcs)`. So
`n=` counts characters, as in CPython, and only the first `n` are split: 200 calls of
`wcswidth(text, 3)` on 100,000 characters take 0.002 s of CPU, where splitting all of them took
0.35 s (CPython: 0.04 s). The helper tests `_UTF8_STR = len('\u00e9') == 2`, so under CPython
each item is one character and the edited module prints what upstream prints. `wcwidth()` needs
no edit: it takes one character, and `ord()` of a string of two characters raises CPython's
`TypeError` (`ord() expected a character, but string of length 2 found`).

**Outside the roadmap: `operator.index()`.** `_clamp_ambiguous_width()` called
`operator.index(ambiguous_width)`, which rejects a `float`; Pystachy's `lib/operator.py` calls
`int.__index__`, which Pystachy's `int` lacks (`'int' has no method '__index__'`). The value is
`ambiguous_width` itself: the parameter is an `int`, and Pystachy rejects a `float` argument at
compile time. (CPython running the edited module would accept `ambiguous_width=2.0`, where
upstream raises `TypeError`.)

**Build time: `table_grapheme.py` keeps the 4 tables the two functions read** (the regional
indicators, the extended pictographics, the viramas and the invisible stackers, 198 ranges) and
leaves out the other 16 (2,038 ranges), in 3 regions; `_wcswidth.py` no longer imports
`GRAPHEME_EXTEND`, read only by `_scan_zwj_cluster_end()` for `wcstwidth()`. Pystachy builds each
table at import with straight-line code, one allocation per range, which the AOT build's
`clang -O2` takes long to compile: with the whole file, building a program that imports `wcwidth`
takes 5.8 s of CPU, against 3.2 s with these 4 tables (see Speed).

## What compiles as it is

`wcwidth()`, `bisearch()` and the grapheme logic of `wcswidth()` are upstream's but for the edits
above: the early return for printable ASCII, the C0 and C1 tests, `ord(wc) if wc else 0`, chained
comparisons, the virama, ZWJ, VS15/VS16, regional indicator and Fitzpatrick states,
`n: Optional[int] = None` with `min(n, len(...))`, and the `unicode_version` parameter, accepted
and ignored. Also as they are: six of the seven table modules, dicts keyed by the Unicode version
whose values are tuples of up to 343 `(int, int)` pairs, and the import of each name from them;
`from __future__ import annotations`; `__lazy_modules__` lists that name modules the port leaves
out, and `_constants.py`'s `__all__`; the `try`/`except ImportError`/`else` that looks for
the C extension; `_clamp_ambiguous_width()`'s clamp to 1 or 2; the re-exports of `__init__.py`
(`ZERO_WIDTH`, `WIDE_EASTASIAN`, `AMBIGUOUS_EASTASIAN`, `VS16_NARROW_TO_WIDE`, `_bisearch`,
`list_versions`, `_wcmatch_version`) and `__version__`. Functions that use what the port leaves
out stay in the source, unedited: Pystachy compiles a function only where a program calls it.

## What the port leaves out

- **`wcstwidth()`**, `list_term_programs()` and `resolve_terminal()`: the per-terminal
  corrections. `wcstwidth` and `list_term_programs` are imported as upstream imports them, and a
  call is rejected at compile time (`wcwidth._wcswidth.wcstwidth() is not supported: parameter
  'term_program': unsupported type annotation`, for `bool | str`); they need M1 and M4, sets (M7),
  and `importlib` and `functools` (#11).
- **The rest of the API**, whose modules are not imported: `width()`, `ljust()`, `rjust()`,
  `center()`, `wrap()`, `clip()`, `iter_graphemes()`, `iter_sequences()`, `strip_sequences()`,
  `propagate_sgr()` and the `Hyperlink` and `TextSizing` classes. They need `re`
  (`escape_sequences.py` compiles 10 patterns, and three more modules import it), generators and
  `itertools`, `enum.IntEnum`, a `textwrap.TextWrapper` subclass and many `lru_cache` decorators:
  native hubs (#11), inheritance (M2, [#7](https://github.com/den-run-ai/pystachy/issues/7)), M3
  and M7.
- `_wcversion_value()`, deprecated, which returns `tuple(map(int, ...))` (M1, M3).
- The C extension (`HAS_C_EXTENSION` is `False`). `wcwidth.cache_info()` counts other entries than
  upstream's after `wcswidth()`: for `ambiguous_width=1` upstream calls `wcwidth(char)`, through
  the variable `_wcwidth` (above), and this port `wcwidth(char, 'auto', 1)`, a form of call that
  `lru_cache` keys apart.
- Arguments that CPython accepts and Pystachy rejects at compile time: a `bool` `ambiguous_width`
  (`wcswidth("¡x", ambiguous_width=True)` is 2 in CPython, whose `operator.index()` takes a
  `bool`; Pystachy: `expected int, got bool`), and a `float` one, which upstream rejects at run
  time with `TypeError` (Pystachy: `expected int, got float`); a `bool` `n`
  (`wcswidth("abc", True)` is 1 in CPython; Pystachy: `expected int | None, got bool`).

## Deviations it hits

- **`str` is UTF-8 bytes** ([docs/language.md](../../docs/language.md#deviations-from-cpython)).
  With the edit above, `wcwidth()` and `wcswidth()` give CPython's widths for any text, and `n=`
  counts characters. What a program computes from a `str` itself still counts bytes: `n` from
  `len()` (`wcswidth("中文", len("中"))` is 4, CPython: 2, since `len("中")` is 3), and the characters
  of a `for` loop over a `str`, as in upstream's tests' `map(wcwidth, phrase)`:
  `[wcwidth(c) for c in "€"]` is `[1, -1, 1]` (CPython: `[1]`), the widths of the bytes 0xE2, 0x82
  and 0xAC read as Latin-1 characters. Text cut inside a character by a slice keeps the bytes
  left over, each read the same way, 0x80-0x9F as C1 controls: `wcswidth("中文"[:4])` is 3
  (CPython: 4), the width of "中" and of the lead byte 0xE6 as "æ", and `wcswidth("中文"[4:])` is
  -1 (CPython: 0). `chr()` below 256 makes one byte, measured as CPython measures that code point
  (`wcswidth(chr(0xE9) + "ab")` is 3 in both), unless such bytes make a UTF-8 sequence:
  `chr(0xC3) + chr(0xA9)` is "é" in Pystachy, 1 cell, and "Ã©" in CPython, 2. Text that is all
  ASCII is not affected.
- **`int` is 64-bit.** The arithmetic is on code points, at most 0x10FFFF, and widths. `n` and
  `ambiguous_width` are compared, never computed on; the tests pass 2**63 - 1 and -(2**63 - 1) for
  both. A program cannot make a bigger argument: `wcswidth("abc", 2 ** 63)` is 3 in CPython, and
  Pystachy raises `OverflowError: integer result does not fit in 64 bits` computing `2 ** 63`.

## Tests

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

## Speed

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

**The cache of `wcwidth()`.** Compiled, `wcwidth()` takes less time than a lookup in its cache:
an ASCII character returns at its first test, and another is a few binary searches of tables of
ints, where a lookup makes, hashes and compares the key `(form, char, 'auto', ambiguous_width)` and
moves its link. So the decorator costs time here, where it saves it under CPython. A workload of
20,000 rounds of `wcswidth()` at both ambiguous widths over four lines of mixed text (CJK, a ZWJ
family, VS16, a flag, a skin tone, Katakana, fullwidth Latin, a Devanagari conjunct, Thai,
ambiguous characters, Cyrillic, Hebrew, accented Latin, ASCII), then `wcwidth()` of each code
point from 0x100 to 0x2FFFF, all misses for `maxsize=1024`; medians of 5, AOT:

| | `wcswidth()` rounds | `wcwidth()` of 196,352 code points |
|---|---:|---:|
| this port, decorators commented out | 0.156 s | 0.005 s |
| this port, decorators as upstream's | 0.298 s | 0.030 s |
| the same, with #267 (a tuple key's items hashed in place) | 0.235 s | 0.023 s |
| CPython 3.13.16, unmodified wcwidth 0.9.2, pure Python | 0.84 s | 0.32 s |

With the cache, the port runs 1.9 times as long as without it (1.5 with #267), and still 2.8
and 11 times faster than CPython (3.6 and 14). A miss, which evicts here, hashes its key four
times, in the lookup, the check after the call, the eviction and the insertion, as CPython's C
code looks the key up four times, with its hash computed once. Commenting the decorator out
again would be an edit for speed, not for Pystachy. Building `tests/port_wcwidth_core.py` takes
3.6 s with the cache, 3.3 s without (medians of 3).

**Build time.** `pystachy build` of a program that imports `wcwidth` and calls `wcwidth()` once
takes 3.2 s of CPU (3.2 s of wall clock, at load 5 to 6), against 0.15 s for `print(1)`;
`tests/port_wcwidth_core.py` takes 3.6 s and `tests/port_wcwidth_edges.py` 3.7 s (medians of 3,
wall clock about the same; 4.0 and 4.2 s of CPU with the compiler collecting every 1,000
allocations). Of the 20,000 lines of LLVM IR of a test, 10,200 build the port's tables (1,245
ranges) at import, and 5,700 are `_constants.py`'s import, where `list()` of a tuple and a `for`
over one copy the tuple's items with one call each (1,040 calls). With `table_grapheme.py` as
upstream ships it (3,283 ranges in all), the program above and `port_wcwidth_edges` take 5.8 s and
6.2 s of CPU to build. `pystachy ir` alone takes 0.1 s of CPU.
