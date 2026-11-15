# Independent enum null-denominator review

Candidate: `0a2fe77a580106c197face4d2904be80e3f85dbc`. Baseline: `950c0440ad793dc6c34664f591383a5e6bba14dd`.

All 49 fewer null-removal obligations across 11 enum fixtures have exact typed-specialization attribution. Their old sites all removed a `NoneType._value_` guard. This is a review of the retained diagnostic snapshots, pending exact binding to the fresh final-source census.

## Symbol identity matters

In `lib_enum_plain_isinstance`, seven old symbols disappear and five names are reused for different signatures: `StrEnum.__eq__.1/.2` change `other` to `Any/dyn`; `_str_of.1/.2` change `x` to `Any/dyn`; `_int_of.3` changes `(IntFlag, IntEnum, str) -> int` to `(Any, IntFlag, str) -> Any`. The 12 old typed specializations carrying one guard each are absent.

In `lib_enum_intflag`, the raw symbol delta alone would be misleading. Old `_int_of.3` `(I, Number, str) -> int` survives as new `_int_of.2`, retaining its identical one-site null-removal obligation. The actual lost helper specialization is old `_int_of.2` `(I, I, str) -> int`, alongside `IntEnum.__eq__.1` `(Number, I)` and `IntFlag.__eq__.3` `(I, I)`. These account for the net decrease of three. Full old/new typed functions and null passes are retained separately.

| Fixture | Fewer null-removal obligations |
| --- | ---: |
| exit_enum_member_caught.py | 2 |
| exit_enum_stored_reflection.py | 2 |
| exit_intflag_stored_mutated.py | 2 |
| exit_intflag_stored_zero.py | 2 |
| lib_enum_any.py | 14 |
| lib_enum_flag_bits.py | 2 |
| lib_enum_flag_numeric_lookup.py | 2 |
| lib_enum_flag_width.py | 6 |
| lib_enum_format_str.py | 2 |
| lib_enum_intflag.py | 3 |
| lib_enum_plain_isinstance.py | 12 |

The review rehashed each raw snapshot and extraction, matched all compact function/null-pass excerpts to the raw snapshots, verified exact old removed operations and their absence after the recorded pass, and matched the per-program arithmetic. No broad normalization was used. No execution or theorem-checker verdict was produced; final census binding and semantic approval remain separate.
