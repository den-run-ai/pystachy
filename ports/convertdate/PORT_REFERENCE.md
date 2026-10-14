# convertdate 2.5.1: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `convertdate-2.5.1.tar.gz`. License: MIT; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `8ade438cced7eae579e622f3f54354e52609840f597f7b09a16d7789a15d4e0a`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `f74977814036547b4971fb513771e96c0a10e3900d311e5972bcdac3d0a4d851` | 6 (8 lines) |
| `armenian.py` | `9656af80fa6147c8d1c185ce2aeed353ba19da75c3ddb324a34b58f034ffb9f6` | 2 |
| `coptic.py` | `708c59f6ded28f4203e13c673ab9eede2f37df8370c3133e05f3a2b7d27443a2` | none |
| `daycount.py` | `4a27c7e2fd2c0a95187364fd3b535ea622d1671bee08da55fbfbf7a3d1880b32` | none |
| `gregorian.py` | `5d64d4f49fc4136226de04f6e743989aaaad05d86ba90fb7a7d8d16417a343f4` | 3 |
| `hebrew.py` | `bb313d4fc99844a0dd86d4330cb155d59a606ca012acb4a1d02ef53047d7b3b9` | 7 |
| `holidays.py` | `a41e4a1e52bf094413fb3a95ff391be715a9a2c2bb6276ff97303aa357ec4e93` | 3 |
| `indian_civil.py` | `a552ddac630ff4414d1251c8e1b4b5dee1ac445bff6c50f28dea9da7f344d16e` | 2 |
| `islamic.py` | `07ed8f5cebab7eda274153f28f32fc572469444fcf71e28f2d4ef41303813871` | 1 |
| `iso.py` | `e0275328f1b3c3f59236b28d17cfc18a8336d2c0aff117bfbde1384d50c3ac9c` | 2 |
| `julian.py` | `7d80a2e7d892d2227f19b525e925c639b35eb0cefffdc411c667b9a38c2f1897` | 3 |
| `julianday.py` | `46eb3e618a0e5932acfe32b3861a95f9c354c19e9bd85d49943ae1c9902bbd0a` | 1 |
| `mayan.py` | `c27e20a1352832aec78172fb2d8b1c10b7be6e65868ddc6c70a9f9f97654e02d` | 1 |
| `ordinal.py` | `3d0edd000322c4bd5dea6227b51f7618955352117eb2fe047ca63914bd558008` | 1 |
| `positivist.py` | `60c3c533530bb29fcad3b7d0714bc06f5385fef59e342db0fb0eeadeb5c0fc1d` | 3 |
| `utils.py` | `c6bc8f4df101e7866a6b4dec242357c89e866e1ea7e5017243a3343791926c68` | 5 |
| `data/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty) | none |
| `data/positivist.py` | `1008b71b7ce4d8f910dbb5ac075a100d6f7f9ff145a0b41496c49a1a8fb87df2` | none |
| `_calendar.py` | not convertdate's: the local calendar/date-arithmetic adapter | |

## Adaptation record

- Forty marked edits in fourteen files preserve the conversion algorithms: numeric locals keep one static type and mutually recursive Hebrew functions have explicit return types.
- `_calendar.py` supplies the small calendar/date-arithmetic API the port uses, with CPython input checks and the exception-base difference documented in the guide.
- Imports and exports omit the PyMeeus calendars and Dublin API; unused datetime/formatting/generator paths remain outside the validated coverage.
- Optional lists are built with one consistent item type; error messages use f-strings, and Easter conversion passes fixed tuple items explicitly.

## Validation snapshot

`tests/port_convertdate_calendars.py` calls `hebrew.year_days()` before any other function of
`hebrew` (the mutually recursive return-type case), then takes 21 Gregorian dates to Julian days and to each
calendar and back: the Gregorian reform (1582-10-04 and 10-15), leap days and century years
(1900, 2000, 2100), the years 1, 0 and -500, Julian day 0 (-4713-11-24), 9999-12-31, the
Islamic, Coptic, Positivist and Mayan epochs and 2012-12-21 (13.0.0.0.0). It round-trips 430
consecutive days from 2023-09-01 (a Hebrew leap year with Adar I and II, the 13th months of the
Coptic and Armenian years, the Indian year's start) through eight calendars, printing the days
that begin a Hebrew, Islamic, Coptic, Indian or Armenian month, and every 997th day from the
year 1 to 2999 through seven, and Armenian (in both methods) and Positivist from their epochs
(0 mismatches). It prints month lengths, leap years and month calendars of seven calendars,
the Mayan haab and tzolk'in, ISO weeks (years of 52 and 53), ordinal dates, `julianday`, the
weekday helpers of `utils` with a float and an int Julian day (the verifier's `n_weeks()` case:
an int stays an int), int Julian days through `julian`, `hebrew`, `islamic` and `indian_civil`
(the separated floating-point locals) and `julianday.to_julian()`, and 14 error paths, among them a bad month
caught by `except IndexError` and `except LookupError` (the verifier's `IllegalMonthError` case).

`tests/port_convertdate_holidays.py` prints every holiday function for 10 years (1939 to 1941,
when US Thanksgiving moved, and 7 years from 1999 to 2100), with `observed=True`, `eve=True` and
the Canadian and Mexican variants; Easter in the three churches every third year from 1 to 2998;
observed holidays of years outside 1..9999, which `calendar.weekday` counts modulo 400;
`utils.nth_day_of_month()` with the last weekday (`n=0`) and 7 calls that raise `IndexError`;
a float year, which `new_years(2023.0)` keeps and with which `new_years(2023.0, True)`,
`thanksgiving(2024.0)`, `utils.nth_day_of_month()` and `gregorian.month_length()` raise
`TypeError` from `calendar.weekday()`; and the `ValueError`, `NotImplementedError` and
`DeprecationWarning` that `easter()`, `thanksgiving()` and `columbus_day()` raise.

`tests/port_convertdate_star.py` takes the package's modules with `from convertdate import *`
and calls a conversion of each calendar; the import stopped at `bahai` while `__all__` named
the four modules the port leaves out.

`tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under CPython against
the unmodified upstream package (with PyMeeus 0.5.12 on the path, as its `__init__.py` imports
`bahai`, `french_republican` and `persian`, which the tests do not call), the first two print
exactly what they print against this port. Both are small: under `make verify`'s gc-stress stage
(the compiler collecting every 1,000 allocations, the program at every allocation), each takes 3
to 6 s for the JIT run and the AOT build and run together, and each AOT build 2 to 4 s.

## Benchmark snapshot

The headline workload: 73,000 consecutive days from 1900-01-01, each taken from its Julian day
to the Gregorian, Hebrew, Islamic, Julian, Coptic and Indian civil calendars, and back to a
Julian day from the Hebrew and the Islamic date (0 mismatches, and the same output in both).
Wall clock with process start-up, and the CPU time (user + system), median of 3 runs, on a
4-core x86-64 VM that was running other jobs (a load average of 4 to 5):

| | wall clock | CPU time |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.211 s | 0.210 s |
| CPython 3.13.16, unmodified convertdate 2.5.1 | 5.241 s | 5.200 s |

That is 24.8 times faster (24.8 in CPU time). Two more sets of runs, at load averages of 3 to 4,
gave 0.220 s and 5.176 s (23.5 times) and 0.213 s and 5.089 s (23.9 times); runs of the port
before the integer-Julian-day adaptations, at load averages of 4 to 9, gave 24 to 27 times, and the evaluation of
the port, on the same VM two days before, 0.212 s and 4.940 s (23 times).
convertdate has no C extension, so CPython runs it in the interpreter; about 0.1 s of CPython's
time is the import of convertdate and PyMeeus.
