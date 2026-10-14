# sgp4 2.27: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `sgp4-2.27.tar.gz`. License: MIT; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `06d37247c6985739b707b8b39b6b83e06e8af783b2531e31965501ba983985f9`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `8f01018363382658c82ae05408e8fb00e077c02be3b6a857478205f887da6b0e` | none |
| `alpha5.py` | `98b6a004d971f25f837a0efa1f073e6bc6a36314fd1448b3078473db9ab4267a` | none |
| `api.py` | `e61f7a4b1ddd026a0cfd147ef18cf2eaf1aee9e05eae9098677cbd811f519bf3` | none |
| `earth_gravity.py` | `70057a3a1ed33c96b8c191c28c4012b4d2fdbd55b5775ec9bdaaabf78f418879` | 2 |
| `ext.py` | `31240fe331e03d3427adf8afc113838a6a09ab769d5c484b8c13c7cbf1fc6287` | 2 |
| `functions.py` | `8947e790097ae705f35244a3233a8b0ec61b214873618a241488686993b79e40` | 1 |
| `io.py` | `8adb8030c909d0bce36c2ea22dd96fbe8eaff19415afb3da22872df62ff8302e` | 7 |
| `model.py` | `8725b573ea25f33497022dcab447a139d3ee3eb71e0894da52658877ce6cc324` | 10 |
| `propagation.py` | `fa851ca7d8710eb54d684de61bc84cc8a3687241518e4ee4cfe8249e0fb33a92` | 6 |

## Adaptation record

- Satrec’s slots become declared typed fields; exposed methods are annotated, and datetime validation is retained through `_check_datetime()` without constructing the omitted epoch object.
- Gravity constants use a typed `NamedTuple` and a list of gravity models; fixed tuple items are passed explicitly.
- Numeric/text temporaries are separated instead of rebinding one variable to unrelated types. Error messages use f-strings/replacements.
- The 2,069-line propagator needs six small edits; the remaining adaptation is in model construction and API plumbing.

## Validation snapshot

`tests/port_sgp4_verify.py` runs sgp4's official verification as its own test suite does
(`test_satrec_against_tcppver_using_julian_dates` in the sdist's `tests.py`), on 5 of the 33
satellites of `SGP4-VER.TLE`, 16 of the 700 lines that Vallado's C++ SGP4 wrote to
`tcppver.out`, which it embeds, and 2 of the 7 errors that `tests.py` expects: 00005 (SGP4),
08195 (SDP4, a Molniya orbit in 12-hour resonance), 28626 (SDP4, geosynchronous), 28872 (SGP4
with a low perigee, which decays: error 6 at 55 minutes) and 33334 (error 3 at its epoch). It
prints each line it computes with `Satrec.twoline2rv()`, `Satrec.sgp4(jd, fr)`, `invjday()` and
`rv2coe()`, and compares it with the official one as the suite does: positions and velocities to
2e-7, the other fields as text.
`tests/port_sgp4_api.py` runs the cases of an evaluation of the port and of an independent check
of it: the fields of the ISS's TLE, `sgp4(jd, fr)` and `sgp4_tsince()`, the three gravity
models, times far from the epoch (error 1, NaN), a satellite that decays (`SGP4_ERRORS`),
`Satrec.sgp4init()` in both operation modes, Alpha-5 numbers up to 339999 and the
`ValueError` beyond, malformed TLEs with their complete messages (braces in a line, short and
empty lines, mismatched satellite numbers, non-ASCII characters, a revnum or an ephtype that is
not a number), epoch fields that `datetime()` rejects (the `_check_datetime()` adaptation), `jday()`, `days2mdhms()` and
`invjday()` at the edges, and `rv2coe()` on degenerate orbits; it ends with a `ValueError` that
nothing catches. `tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under
CPython against the unmodified upstream package, both print exactly what they print against this
port.

Outside the tests, the evaluation's program for the whole verification regenerates all 700 lines
of `tcppver.out` from `SGP4-VER.TLE` with this port: 0 mismatches, the errors `[1, 1, 6, 6, 4,
3, 6]` that `tests.py` expects, and the same 700 lines as CPython, JIT and AOT. The tests are
small: under `make verify`'s gc-stress stage (the compiler collecting every 1,000 allocations,
the program at every allocation), each takes 3.7 to 7.2 s for the JIT run and the AOT build and
run together, and its AOT build 2.0 to 3.4 s (2.6 to 4.7 s under gc-stress), on a 4-core VM at a
load of 11 to 18.

## Benchmark snapshot

The headline workload, the evaluation's: the ISS (SGP4) and a Molniya orbit (08195, SDP4)
propagated every second for 3 days with `Satrec.sgp4(jd, fr)`, 518,400 propagations, summing
the positions (the same sum in both). Wall clock with process start-up, and the CPU time (user
+ system), median of 5 runs, on a 4-core x86-64 VM that was running other jobs (a load average
of 10 to 13):

| | wall clock | CPU time |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.439 s | 0.355 s |
| CPython 3.13.16, unmodified sgp4 2.27 (pure Python) | 3.557 s | 3.007 s |

That is 8.1 times faster (8.5 in CPU time); earlier sets of runs gave 7.2 to 8.2 times (8.5 to
8.6 in CPU time), and the evaluation of the port, on the same VM two days before, 0.352 s and
3.033 s (8.6 times). CPython runs sgp4's pure-Python modules here, as it does where the C++
extension is missing; with the extension of sgp4's wheels (`accelerated` is `True`), CPython
propagates with Vallado's compiled C++ code instead, which this does not compare.
