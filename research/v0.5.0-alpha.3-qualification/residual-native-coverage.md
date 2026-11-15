# Native coverage of every added residual fixture

All 12 fixtures with newly recorded Lean residuals passed both retained native JIT and AOT in CI run 43681595990: 24 fixture executions. This is bounded runtime evidence; it does not satisfy the failed strict-storage gate or discharge any proof obligation.

| Fixture | JIT job / line / ms | AOT job / line / ms |
|---|---|---|
| `tests/deviations/complex_union_none.py` | 132714325039 / 495 / 60 | 132714325032 / 248 / 253 |
| `tests/programs/inference/dynany_complex_union_identity.py` | 132714325039 / 671 / 136 | 132714325032 / 336 / 338 |
| `tests/programs/library/lib_decimal.py` | 132714325039 / 763 / 1236 | 132714325032 / 382 / 3393 |
| `tests/programs/numbers/complex_union_container_eq.py` | 132714325020 / 800 / 103 | 132714325071 / 400 / 310 |
| `tests/programs/numbers/complex_union_enum_eq.py` | 132714325039 / 800 / 136 | 132714325093 / 400 / 406 |
| `tests/programs/numbers/complex_union_identity.py` | 132714325020 / 801 / 109 | 132714325041 / 401 / 293 |
| `tests/programs/numbers/complex_union_nested.py` | 132714325039 / 801 / 67 | 132714325032 / 401 / 294 |
| `tests/programs/numbers/complex_union_object_eq.py` | 132714325039 / 802 / 66 | 132714325093 / 401 / 249 |
| `tests/programs/numbers/complex_union_tuple_search.py` | 132714325039 / 804 / 94 | 132714325093 / 402 / 313 |
| `tests/programs/numbers/complex_unions.py` | 132714325020 / 805 / 242 | 132714325041 / 403 / 794 |
| `tests/programs/numbers/complex_values.py` | 132714325039 / 805 / 111 | 132714325032 / 403 / 525 |
| `tests/programs/numbers/python_int_optional_tuple_keys.py` | 132714325020 / 821 / 133 | 132714325041 / 411 / 574 |

The six GitHub artifact ZIP hashes match retained API digests. Each extracted verification receipt, selected-case log, post-execution timing log, and zero-failure execution log was checked against its ZIP bytes. The receipts identify synthetic merge e51127bc, whose full tree equals b0bda81ec. The four proof repair files are the entire b0→94f4 difference; source, runtime, fixtures, sidecars and the native harness retain the same bytes.

The complex-null deviation uses its handwritten TypeError oracle. The other eleven fixtures use recorded CPython stdout and exit status. Successful individual cases intentionally emit no PASS line; complete expected counts, zero failures and timing rows establish the executions. All raw file hashes, job URLs, suite counts, source/oracle hashes and artifact identities are retained in the companion JSON.
