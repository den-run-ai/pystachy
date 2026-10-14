# pylev 1.4.0: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `pylev-1.4.0.tar.gz`. License: BSD-3-Clause; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `9e77e941042ad3a4cc305dcdf2b2dec1aec2fbe3dd9015d2698ad02b173006d1`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `abd7f780829ad3ef0dd4f4eeb01ccd048e4dead3bc73a646f0fa5a8461e12463` | none |
| `classic.py` | `b2205250a290e2cf7f125e127bec28c1ea0f7a7387ad3559a841fec40a25d248` | none |
| `recursive.py` | `759d2d7ccbf4205ff0c6e946296d8f8c2eb0a7db503ac3a666f36066087e9088` | 1 line |
| `wf.py` | `160773704d0cee4715faddacb57b35e25bd28a72bbbd4726e11a1eebbf0caef1` | 2 regions (the Python 2 shim) |
| `damerau.py` | `c7e613589dd646f9587fcdcc3301a656bb49db61ea719ddfb3e84a70aced72d9` | 2 regions (the Python 2 shim) |

## Adaptation record

- The Python 2 shim sets `PY2 = False` and removes the unavailable `xrange` branch in `wf.py` and `damerau.py`.
- `recursive.py` annotates its empty memo as `dict[str, int]`. `classic.py` and `__init__.py` are unchanged.
- The old alias-import workaround was removed after the loader fix; the benchmark compares the retained upstream aliases and algorithms.

## Validation snapshot

`tests/port_pylev_strings.py` runs the cases of pylev's own test suite (`tests.py` in its
repository, at the tag of 1.4.0) as a program, every pair in both orders, then edge cases on
every variant and alias: empty strings, the longer string first, adjacent transpositions, NUL
and control characters, `classic_levenshtein` on the short pairs, and the two non-ASCII pairs
where the byte and character distances agree. `tests/port_pylev_sequences.py` runs the
variants on lists of words and of 64-bit ints, and `recursive_levenshtein` with explicit
lengths and offsets (positional and keyword) and with a memo shared between calls, whose keys
do not name the strings (a second call with other strings reads the first one's results, as
upstream does). `tests/port_pylev_imports.py` imports pylev as its users do: a function that
suggests the commands closest to a mistyped name, as clikit's and cleo's do, through
`from pylev import levenshtein`; then the misspelled aliases, `from pylev import *` and the
submodules. `tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under
CPython against the unmodified upstream package, all three print exactly what they print
against this port. All three are small: under `make verify`'s gc-stress stage (the compiler
collecting every 1,000 allocations, the program at every allocation), each takes about 1 s
for the JIT run and the AOT build and run together.

## Benchmark snapshot

The headline workload: `wfi_levenshtein` (the function behind `levenshtein`) and
`damerau_levenshtein` on 6 pairs of strings of 1,500 and 1,400 characters over `acgt`, made by
a linear congruential generator in the program (checksum 9093 in both). Wall clock with
process start-up, median of 3 runs, on a 4-core x86-64 VM that was running other jobs:

| | time |
|---|---:|
| Pystachy AOT executable, this port | 0.360 s |
| CPython 3.13.16, unmodified pylev 1.4.0 | 4.058 s |

That is 11.3 times faster; a second set of runs gave 0.375 s and 3.989 s (10.6 times). pylev has
no C extension, so CPython runs it in the interpreter; programs that need speed under CPython
use a C library such as rapidfuzz or Levenshtein instead, which this does not compare.
