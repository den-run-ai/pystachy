# Use-case readiness, 2026-11-09 (main `f60df76d`, v0.4.0-alpha.2)

| Use case | Correct today | Performance stable | Bugs settled | Share upstream | Share downstream |
|---|---|---|---|---|---|
| [JSON repair](json-repair/README.md) | Yes: 837/837 in CI (x86_64 and aarch64, GC stress) and in a main spot check | No: moved up to 8× between 2 and 9 Nov; not re-measured on the release | No: silent wrong results fixed up to 7 Nov; port is 6 PyPI releases behind | Port: no. One new upstream bug report (stray `/` drops data); a few follow-ups | Narrow claim only; the wheel is not publishable (dev version, `linux_*` tag) |
| [Byte BPE](byte-bpe-and-mypy/README.md) | Yes: byte-identical to CPython in CI and in 12/12 spot checks | Measured once, on 6 Nov (compiler `f7103067`); re-measure on the release | Yes: no issues ever filed; unchanged since 6 Nov | No (nothing for pyperformance; method gaps if presented there) | Yes, with the dated claim and caveats |
| [mypy/mypyc](byte-bpe-and-mypy/README.md#mypy-and-mypyc) | Narrow: NameGenerator and mypyc's 5 tests match; compiler builds under mypyc (7 Nov, `-O0`) | No end-to-end speedup ever shown | Quiet since 4–7 Nov | Not yet (re-run the mypyc build on main first) | Not a use case: nothing to run |
