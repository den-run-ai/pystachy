# jdcal 1.4.1: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `jdcal-1.4.1.tar.gz`. License: BSD-2-Clause; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `472872e096eb8df219c23f2689fc336668bdb43d194094b5cc1707e1640acfc8`.

| file | upstream file and SHA-256 | edits |
|---|---|---|
| `__init__.py` | `jdcal.py`, `a6c5e84e873d794bf0d38c2a32ac3e75653c89823458db7314255c6f40c11871` | 2 lines |

## Adaptation record

- `jcal2jd()` initializes its changing numeric local as a float before subtracting floating-point values.
- `is_leap()` converts the nonzero `math.fmod` result to `bool`, preserving truth while changing the result type.
- These are the module’s two marked source edits. Historical tuple-expansion errors are not a current language support statement.

## Validation snapshot

`tests/port_jdcal_convert.py` runs the cases of jdcal's own test suite (`test_jdcal.py` in the
sdist, run under pytest there) and the examples of its docstrings as a program: `ipart` (and
its `-0.0`), `is_leap` tested for truth, 14 dates from the year -4699 (4700 BC) to 9999 in
both calendars and back through both inverse functions, 11 out-of-range months and days that
carry over (day 0, month 13, negative months and days), round trips, the fraction of the day
(including `jd2gcal(2451545.0, -0.5)`, whose fraction is 1.0 in both), Excel serial dates as
openpyxl computed them, and the suite's random round trip, 1,000 dates drawn by a linear
congruential generator instead of `random`. It leaves out the comparison with ERFA's `cal2jd`,
which needs astropy and numpy, and passes `int(3.5)` where the suite passes 3.5.
`tests/port_jdcal_extremes.py` runs the edge cases an independent check of the port added:
Julian dates up to 1e18 days and down to -1e15, `-0.0`, fractions next to 0.5 and of 1e-300,
years of ±10**9, 10**12, ±2**52 and 2.5e16 in both calendars, the last values each function
takes before a 64-bit int overflows, int arguments to `jd2gcal` and `jd2jcal`, NaN and
both infinities (`ValueError: cannot convert float NaN to integer`), and `is_leap` of negative
years, ±2**62, 2**63 - 1, -2**63 and floats. `tests/run.sh` compares what they print with
CPython's, JIT and AOT. Run under CPython against the unmodified upstream module, both print
exactly what they print against this port. Both are small: under `make verify`'s gc-stress
stage (the compiler collecting every 1,000 allocations, the program at every allocation), each
takes 0.6 to 1.6 s for the JIT run and the AOT build and run together, and each AOT build
0.5 to 1.2 s, by the machine's load (a load average of 3 to 17 on 4 cores).

## Benchmark snapshot

The headline workload: 2,688,000 round trips through all four functions, every day 1 to 28 of
every month of the years -4000 to 3999 taken from the Gregorian calendar to a Julian date and
back, then to the Julian calendar and back to a Julian date (0 mismatches, and the same output
in both). Wall clock with process start-up, and the CPU time (user + system), median of 3
runs, on a 4-core x86-64 VM that was running other jobs (a load average of 8 to 11):

| | wall clock | CPU time |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.628 s | 0.499 s |
| CPython 3.13.16, unmodified jdcal 1.4.1 | 12.042 s | 9.618 s |

That is 19.2 times faster (19.3 in CPU time); a second set of runs gave 0.590 s and 12.205 s
(20.7 times; CPU time 0.497 s and 9.516 s, 19.1 times), and the evaluation of the port, on
the same VM two days before, 0.587 s and 9.353 s (16 times). jdcal has no C extension, so
CPython runs it in the interpreter; programs that need speed under CPython use ERFA's C
functions (`eraCal2jd` and `eraJd2cal`, through pyerfa or astropy), which this does not
compare.
