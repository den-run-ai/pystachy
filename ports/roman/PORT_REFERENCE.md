# roman 5.2: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `roman-5.2.tar.gz`. License: ZPL-2.1; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `275fe9f46290f7d0ffaea1c33251b92b8e463ace23660508ceef522e7587cb6f`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `7d8962ca4ed71a67e0d07d0f6e81deb0f0b177565375d5ff39be1b1dc50e16f5` | 4 regions, and the notice of change |

## Adaptation record

- A small boolean scanner replaces the compiled numeral regular expression without changing its accepted ASCII language, including `$` before one final newline.
- `fromRoman()` calls that scanner. `argparse` is imported lazily in `parse_args()`, whose annotation is quoted.
- Four edited regions and a dated change notice satisfy the ZPL modified-file requirement; conversion algorithms and numeral mappings remain upstream’s.

## Validation snapshot

`tests/port_roman_convert.py` runs the cases of roman's own test suite (`src/tests.py` in the
sdist) as a program: the 20 pairs of its `TEST_MAP` both ways and in lower case, and its errors
(100000 out of range, `''` and `'Q12'` invalid, `'n'` with `special_case=False`). Then it runs
the range's edges (-1, 5000, 2**63 - 1, -(2**63 - 1), -2**63), `N` and `n` and `'N\n'` with
`special_case` given by position and by keyword, the exception hierarchy (`isinstance()`,
`type(e).__name__`, a `NotIntegerError` raised by the program), every number from 1 to 4999
there and back, in upper and lower case, other call forms (`import roman as rm`,
`toRoman as to_roman`, every argument by keyword and in either order), `__author__`,
`__copyright__` and the uses of `romanNumeralMap` that compile, and last an `OutOfRangeError`
that escapes, whose report must match CPython's last line of stderr.
`tests/port_roman_validate.py` runs the validation replaced by the boolean scanner: 59 strings at the
pattern's edges (a group's alternative followed by the letter another one would leave, as in
`CMCM`, `CDC`, `XCX` and `IXI`; too many letters of a kind; `$` before a final newline and not
before two, before `\r\n` or before another line break such as `\r`, `\x0b`, `\x85` and
`\u2028`; a leading newline, spaces, a tab, NUL, `%` signs, 50 M's, and four strings with
characters outside ASCII that have no case), then every string of one to four numeral letters,
2,800 strings of which 347 are valid, with a checksum of their values. They leave out what the
edits remove (the command line, which upstream's tests drive through `sys.argv` and `StringIO`)
and `toRoman('1')`, which Pystachy rejects at compile time.

`tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under CPython against
the unmodified upstream package, both print exactly what they print against this port. Both
are small: under `make verify`'s gc-stress stage (the compiler collecting every 1,000
allocations, the program at every allocation), the JIT run and the AOT build and run take about
2-3 s together for each of them, on a 4-core VM that was running other jobs; each AOT build
takes 0.7-1.5 s.

## Benchmark snapshot

The headline workload: 200 round trips `fromRoman(toRoman(n))` for every `n` from 1 to 4999,
about a million conversions each way (checksum 2499500000 in all three). Median of 5 runs, with
process start-up, on a 4-core x86-64 VM that was running other jobs (load average 5-7):

| | wall clock | CPU time |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.631 s | 0.621 s |
| CPython 3.13.16, unmodified roman 5.2 | 2.353 s | 2.350 s |
| CPython 3.13.16, this port | 2.948 s | 2.940 s |

That is 3.7 times faster. Two more sets of 5 runs gave the same in CPU time (0.629 s against
2.331 s and 2.319 s), and an earlier measurement, median of 3, gave 0.646 s against 2.181 s of
wall-clock time (3.4 times). roman has no C extension, but CPython checks each numeral in its C
regex engine: under CPython the port, whose check is the adapted Python scanner, is slower
than upstream, so the executable runs the code of this port 4.7 times faster than CPython does.
