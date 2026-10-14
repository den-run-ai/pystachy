# sqids 0.5.2: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `sqids-0.5.2.tar.gz`. License: MIT; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `5ac08f0c5c9b6814bc2e7c79ee5931e0849d25d95c50e415771b022a44f58af9`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `dec511d0fd42c1fb20907eba8161abdadf6278c31d1d0b341038e242a204eaa1` | none |
| `constants.py` | `9b0e801cfcd48c0d028669d84a73a174a99f51da57ecc250e464a92eaf8ac1ae` | 2 set displays made lists (4 lines) |
| `sqids.py` | `7e9765b179f1b25e4b9fdf71d606d2048b2a037ed089933d8a2243e67ffb761e` | 12 regions |

## Adaptation record

- Blocklists are lists rather than sets/variable-length tuples; character-membership operations use strings plus `all()`/`any()`.
- Uniqueness checks use character counts; reversed slices become `reversed()` consumers.
- Prefix/suffix tuple checks become per-word loops. This loop is a measured cost when the adapted package runs under CPython.
- The encode/decode/shuffle algorithms and defaults are retained, with marked changes in `constants.py` and `sqids.py`.

## Validation snapshot

`tests/port_sqids_encode.py` runs the cases of sqids's own `tests/test_encoding.py`,
`test_minlength.py` and `test_alphabet.py` as a program:

- the 29 distinct incremental vectors, and `86Rf07` for `[1, 2, 3]`;
- round trips of 11 numbers up to `sys.maxsize`, of `range(100)`, and of numbers at 2**62 and
  2**63 - 1;
- the empty list, and strings that are not ids: `""`, `"*"`, a separator alone or first,
  characters outside the alphabet, a trailing newline, and chunks of 11 characters, the longest
  that can decode here (see the port guide’s 64-bit limitation);
- the out-of-range errors;
- minimum lengths 6 to 13 and 62 to 65, four of the 62-character vectors, five lists at each of
  six minimum lengths up to 255, and the errors for -1 and 256;
- custom alphabets: hexadecimal; `abc`, also with a minimum length of 255; upstream's
  92-character alphabet of letters, digits, punctuation and quotes; one of control
  characters; and all 128 ASCII characters, the longest alphabet. Seven alphabets raise
  errors, two of them the 128 characters with one character twice (the repeated-character alphabet check).

`tests/port_sqids_blocklist.py` runs `tests/test_blocklist.py`, with lists where it passes sets:

- the default, empty and custom blocklists;
- words that block a whole id, part of an id, or either end of one;
- decoding blocked ids, a word of three letters, and `Reached max attempts`;
- the filter, on a lowercase word in an uppercase alphabet, on words with characters outside
  the alphabet, and on words shorter than three characters;
- the verifier's words: upper case, with digits, and non-ASCII;
- words given twice or in other cases, which the adapted lists hold as often as given, and
  words of spaces or of nothing;
- five ids that the default blocklist blocks, by a word at an end and by a word anywhere. Each
  is encoded with both ways of filtering the default blocklist: the prefiltered default lists, and the custom-list filter on a copy of `DEFAULT_BLOCKLIST` or with a copy of
  `DEFAULT_ALPHABET`. They agree.
- the property of `tests/test_round_trip.py`, which hypothesis checks on random inputs, on 40
  fixed ones: an id decodes to its numbers, and when an id of three characters or more is
  blocked, sqids makes another id that also decodes to them.

`tests/run.sh` compares what both programs print with CPython's output, JIT and AOT. Run under
CPython against the unmodified upstream package, both print exactly what they print against this
port. They pass JIT and AOT with `PYSTACHY_IRCHECK=1`, and also with the CPython-hosted
compiler, with `PYSTACHY_OPT=-all`, and in the gc-stress form. The evaluation's and the
verifier's drivers, run against the port, print what CPython prints against upstream, except
for the two compatibility differences in the port guide. The evaluation's driver prints 83 lines of vectors
and edge cases. The verifier's two cover numbers at 2**63, blocklist words, and the default
blocklist filtered both ways over 28,572 numbers.

Each test takes about 0.19 s to run JIT. Its AOT build takes 3.2 s, and the executable then
runs in under 0.01 s. In the gc-stress form, the compiler collects every 1,000 allocations
(`PYSTACHY_GC_STRESS=1000`) and the program collects at every allocation
(`PYSTACHY_GC_STRESS_PROGRAM=1`). There the JIT runs take 0.31 s and 0.36 s, and the AOT builds
and runs take 3.5 s and 3.2 s: 3.8 s and 3.6 s per test in all. These are wall-clock medians of
3 or 5, at a load average near 4 on this 4-core VM.

## Benchmark snapshot

The evaluation's workload makes `Sqids(min_length=8)` with the default blocklist. It then
encodes and decodes 100,000 lists of three numbers (`[i, i * 7919 % 1000003, 42]`) and checks
each decode. It prints `100000 1073142 100000`, here and in CPython. Medians of 3, with process
start-up, on a 4-core x86-64 VM:

| | wall clock | CPU time |
|---|---:|---:|
| Pystachy AOT executable, this port | 1.166 s | 1.062 s |
| CPython 3.13.16, unmodified sqids 0.5.2 | 5.062 s | 4.828 s |
| CPython 3.13.16, this port | 5.895 s | 5.875 s |

That makes the executable 4.5 times faster than CPython on upstream in CPU time, and 4.3 times
in wall-clock time. The load average was near 5 during these runs. An earlier set, at a load
near 13, gave 1.064 s against 4.899 s of CPU time (4.6 times). The evaluation measured 1.036 s
against 4.791 s of wall-clock time on a quieter VM. sqids has no C extension, so CPython runs it
as Python everywhere. The executable's peak RSS is 36 MB, and CPython's is 12 MB.

Under CPython the port is 22% slower than upstream. Most of that, 0.9 s, comes from the per-word prefix/suffix loop: it
calls `startswith()` and `endswith()` once per word in Python, where upstream makes two calls
with the tuple and C loops over it. With the upstream tuple checks restored, CPython
takes 4.970 s. Each id of 8 or more characters is tested against 358 words at each end and 195
words anywhere. With an empty blocklist, the executable takes 0.769 s of CPU time, so the
default blocklist's check costs it 0.29 s.
