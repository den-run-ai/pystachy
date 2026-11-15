# Alpha3 complete Lean census and semantic disposition

Status: **reviewed_with_explicit_model_limits**. The frozen proof source is `0a2fe77a580106c197face4d2904be80e3f85dbc`, tree `107460d5f89bdcf37f2741b233eac0568d82604a`. Its complete tree equals the observed integrated release head `328b945f02788b296d9981d1b44706a2a0092255`. The alpha2 proof source `950c0440ad793dc6c34664f591383a5e6bba14dd` likewise has the exact tree of published alpha2 `80490143498d149d407343ba1cb7aedb1db2d2c5`.

The census covers **2,699 programs** and **196 strict-storage selections**. All 2,550 alpha2 programs and all 175 alpha2 storage selections remain. There are 149 added programs and 21 added storage selections. Every selected program was inspected and every required checker category produced a completed result; no failed or error record is hidden.

Strict storage accepts all **25,816 counted obligations** with no rejected, unsupported or unknown-count storage function. This includes a fresh **142/142** for `python_int_optional_tuple_keys.py`, replacing the earlier complete census's three unknown-count unsupported functions. The earlier 8/8 known subtotal was correctly treated as insufficient.

## Counts and remaining model limits

Each ratio below is proved/countable obligations in that model. An unsupported function with an unknown obligation count is listed separately and does not enter that denominator. Counts overlap in scope across models and are not summed into an overall proof percentage.

| Model | Alpha2 proved / counted | Alpha3 proved / counted | Unknown-count function entries, alpha2 → alpha3 |
|---|---:|---:|---:|
| Dynamic payload reads | 2,583 / 2,583 | 2,760 / 2,760 | 0 → 0 |
| Unchecked list/dict accesses | 86,150 / 86,150 | 86,345 / 86,345 | 0 → 0 |
| Removed null checks | 136,394 / 136,413 | 137,285 / 137,304 | 0 → 0 |
| Closed-union reads | 6,633 / 6,948 | 7,289 / 8,146 | 8 → 8 |
| Union payload bits | 13,284 / 13,533 | 14,358 / 15,016 | 0 → 0 |
| Field initialization | 161,750 / 161,987 | 166,284 / 166,521 | 426 → 427 |
| Collector scanning | 190,869 / 191,244 | 194,307 / 194,685 | 9 → 9 |
| Promoting-int fit claims | 187 / 187 | 344 / 344 | 0 → 0 |
| Promoting-int inline arithmetic | 1,692 / 1,692 | 2,784 / 2,784 | 0 → 0 |
| Promoting-int storage | 18,582 / 18,582 | 25,816 / 25,816 | 0 → 0 |

All exact raw residual dictionaries in shared programs remain unchanged, without temporary-name or specialization-suffix normalization. No shared counted gap or unknown-count entry grows. New coverage retains these explicit limits:

- Nine complex fixtures add 21 rejected functions: **542 union reads and 409 payload-bit obligations remain unproved**. Every retained first diagnostic is consistent with the adapter's conservative extra null for `_pystachy_complex$complex`. The review retains callers, normal boxed returns, tuple/list transport and the exact emitted operations; it does not prove all later obligations in each rejected function. Payload-bit totals use the same function verdict and are intentionally listed with union functions.
- `complex_values.py` exposes **three rejected GC obligations** in the existing heterogeneous memo-get protocol. Its body and source contract match the known alpha2 helper under narrowly verified metadata/string bindings. All three remain rejected.
- `lib_decimal.py` adds **one field-initialization function with an unknown obligation count** because prototype inference exceeds its resource bound. Native passes do not convert it into an accepted proof.

The user's earlier statement about three unchanged GC gaps concerns the focused `lib_enum.py` fixture. Those same three remain unchanged there; the full-corpus GC counts and unknown functions are shown in the table above.

## Every decreased denominator

All 38 decreases have exact side-specific snapshots, adapter module identities, per-function sites and independent semantic review. The final fresh census independently matches every candidate snapshot hash and count; the alpha2 side matches its historical census exactly. The 37 null/GC/storage pairs were inspected in 29 programs before the fresh census and then bound by the final verifier. The remaining access pair has a separate exact emitted-IR/runtime contract review.

### Enum null checks: 49 fewer obligations across 11 fixtures

Typed enum comparison dispatch no longer emits some library comparison/helper specializations and their `_value_` null-check removals. The review matches complete parameter and return signatures. In `lib_enum_plain_isinstance`, five retained names now denote Any/dyn specializations while seven other old names are absent. In `lib_enum_intflag`, the old `_int_of.3` specialization survives as `_int_of.2` with the same typed signature and null-removal site; the actually lost specialization is the old `_int_of.2` for the other signature. Literal name arithmetic is preserved but is not substituted for semantic identity.

### Tomllib null checks: 21 fewer removals across seven fixtures

The three checks per fixture are on **Output.flags receivers**, loaded from field 1, before `Flags.add_pending`, the second `Flags.is_`, and `Flags.unset_all`. Failure raises **AttributeError** with the corresponding method message. The exact same checks appear in both before-pass inputs; they are absent after the old pass and retained after the new pass. The `Flags.is_` effect summary now includes object reads/writes through VTuple slicing, so a later heap reload no longer inherits an earlier nonnull fact across that call. These checks remain at runtime rather than contributing removed-check proof obligations. Earlier tuple-pointer/TypeError wording is explicitly corrected in the retained correction history.

### GC helpers: 102 fewer obligations across 16 fixtures

Eighteen unreferenced internal `mappingproxy.__ror__` bodies disappear. Each old symbol has exactly one occurrence in its full LLVM module—the definition—and no call or address reference. The mappingproxy library source is unchanged. The separate four-obligation GC decrease below comes from the deliberately edited identity deviation fixture.

### Storage and moved identity observations

`dynany_identity_boundary.py` removes the formerly failing typed-VTuple and optional-float-list observations after their support is added, leaving the union-list and wide-integer observations. The removed storage site is the low word of the parsed `int("1000")`; the four removed GC sites are the optional list's append, global store and two reads. Positive promoting-int coverage is specifically `python_int_vtuple_identity.py` (both directives, `int("1000")`, repeated entries, list conversion and checked helpers), with optional integer-container and ordinary optional-float-list fixtures covering their respective scopes. The original edited source was separately recompiled and audited; this is not described as unchanged input coverage.

`python_int_vtuple_materialization.py` is unchanged source. Its net storage decrease **46→37** is `optional` **18→7** (-11) plus `small` **6→8** (+2); the other three functions stay at 8/6/8. Removing the intermediate fixed tuple eliminates twelve marker/narrow/decode obligations. Identity capture adds one low-word use in `optional` and two in `small`. Both final overflow guards remain in each function, as do item evaluation and direct VTuple materialization. It is not simply nine deleted sites.

### One unchecked access moves to runtime bounds checking

In `dynany_iter_errors.py`, the final `[1, None]` loop uses `pys_list_get_identity` and `pys_list_get`; both call `idx()` before indexing. Its former unchecked backing-array read no longer enters the Lean unchecked-access count. The earlier action-loop unchecked read remains proved. The C-helper bounds contract is retained source evidence, not a newly granted Lean theorem.

## Exact decrease rows

| Program | Category | Alpha2 proved / counted | Alpha3 proved / counted | Denominator change | Review |
|---|---|---:|---:|---:|---|
| `tests/deviations/dynany_identity_boundary.py` | gc | 8 / 8 | 4 / 4 | -4 | storage |
| `tests/deviations/dynany_identity_boundary.py` | storage | 2 / 2 | 1 / 1 | -1 | storage |
| `tests/deviations/lib_types_mappingproxy_eq_other.py` | gc | 9 / 9 | 6 / 6 | -3 | gc_helpers |
| `tests/programs/apps/port_tomli_w_ini2toml.py` | gc | 168 / 168 | 162 / 162 | -6 | gc_helpers |
| `tests/programs/apps/port_tomli_w_tables.py` | gc | 1372 / 1372 | 1366 / 1366 | -6 | gc_helpers |
| `tests/programs/apps/port_tomli_w_values.py` | gc | 564 / 564 | 558 / 558 | -6 | gc_helpers |
| `tests/programs/exceptions/exit_enum_member_caught.py` | null | 5 / 5 | 3 / 3 | -2 | enum |
| `tests/programs/exceptions/exit_enum_stored_reflection.py` | null | 32 / 32 | 30 / 30 | -2 | enum |
| `tests/programs/exceptions/exit_intflag_stored_mutated.py` | null | 6 / 6 | 4 / 4 | -2 | enum |
| `tests/programs/exceptions/exit_intflag_stored_zero.py` | null | 4 / 4 | 2 / 2 | -2 | enum |
| `tests/programs/inference/dynany_iter_errors.py` | access | 2 / 2 | 1 / 1 | -1 | access |
| `tests/programs/library/lib_enum.py` | gc | 289 / 292 | 277 / 280 | -12 | gc_helpers |
| `tests/programs/library/lib_enum_any.py` | null | 14 / 14 | 0 / 0 | -14 | enum |
| `tests/programs/library/lib_enum_flag_bits.py` | null | 17 / 17 | 15 / 15 | -2 | enum |
| `tests/programs/library/lib_enum_flag_numeric_lookup.py` | null | 7 / 7 | 5 / 5 | -2 | enum |
| `tests/programs/library/lib_enum_flag_width.py` | null | 12 / 12 | 6 / 6 | -6 | enum |
| `tests/programs/library/lib_enum_format_str.py` | null | 4 / 4 | 2 / 2 | -2 | enum |
| `tests/programs/library/lib_enum_intflag.py` | null | 13 / 13 | 10 / 10 | -3 | enum |
| `tests/programs/library/lib_enum_mixin.py` | gc | 83 / 83 | 77 / 77 | -6 | gc_helpers |
| `tests/programs/library/lib_enum_plain_isinstance.py` | null | 24 / 24 | 12 / 12 | -12 | enum |
| `tests/programs/library/lib_tomllib.py` | gc | 705 / 705 | 699 / 699 | -6 | gc_helpers |
| `tests/programs/library/lib_tomllib.py` | null | 753 / 759 | 750 / 756 | -3 | tomllib |
| `tests/programs/library/lib_tomllib_boundary.py` | gc | 689 / 689 | 683 / 683 | -6 | gc_helpers |
| `tests/programs/library/lib_tomllib_boundary.py` | null | 736 / 736 | 733 / 733 | -3 | tomllib |
| `tests/programs/library/lib_tomllib_dynamic.py` | gc | 677 / 677 | 671 / 671 | -6 | gc_helpers |
| `tests/programs/library/lib_tomllib_dynamic.py` | null | 751 / 751 | 748 / 748 | -3 | tomllib |
| `tests/programs/library/lib_tomllib_flags.py` | gc | 679 / 679 | 673 / 673 | -6 | gc_helpers |
| `tests/programs/library/lib_tomllib_flags.py` | null | 731 / 731 | 728 / 728 | -3 | tomllib |
| `tests/programs/library/lib_tomllib_typed_callback.py` | gc | 555 / 555 | 549 / 549 | -6 | gc_helpers |
| `tests/programs/library/lib_tomllib_uncaught.py` | gc | 679 / 679 | 673 / 673 | -6 | gc_helpers |
| `tests/programs/library/lib_tomllib_uncaught.py` | null | 731 / 731 | 728 / 728 | -3 | tomllib |
| `tests/programs/library/lib_types_mappingproxy.py` | gc | 131 / 131 | 119 / 119 | -12 | gc_helpers |
| `tests/programs/library/lib_types_mappingproxy_opaque.py` | gc | 14 / 14 | 11 / 11 | -3 | gc_helpers |
| `tests/programs/numbers/python_int_vtuple_materialization.py` | storage | 46 / 46 | 37 / 37 | -9 | storage |
| `tests/programs/upstream/upstream_tomllib_data.py` | gc | 747 / 747 | 741 / 741 | -6 | gc_helpers |
| `tests/programs/upstream/upstream_tomllib_data.py` | null | 731 / 731 | 728 / 728 | -3 | tomllib |
| `tests/programs/upstream/upstream_tomllib_misc.py` | gc | 695 / 695 | 689 / 689 | -6 | gc_helpers |
| `tests/programs/upstream/upstream_tomllib_misc.py` | null | 736 / 736 | 733 / 733 | -3 | tomllib |

## Execution, provenance and historical failures

The final census started with new records on the frozen storage-repair source, using one worker and a 300-second inspection timeout. The five identified Lean executables were physically copied only after all 19 Lean theorem/build inputs matched their recorded binary origin. The maintained report header and resume checks directly pin the boundary/access binaries; the separate qualification preparation and independent audit pin all five binaries, including int/alias/companion. Any resume also requires an explicit all-five-binary preflight. The three changed Python checker/report inputs are bound to the two reviewed repair manifests. No record or header from an earlier checker source was reused. Any supported same-source resume is explicitly listed in `final-census-receipt.json`, with its exact preserved prefix and per-attempt source identity; no interrupted run is silently presented as uninterrupted.

The original b0 partial census remains interrupted and incomplete. The complete 94f4 census remains a strict-storage failure despite its known 25,682/25,682 subtotal, because three storage functions had unknown counts. Its primary report-process -9 and earlier isolated inspection -9 exits are preserved with unknown causes; RSS samples alone are not OOM attribution. The final storage repair is separately reviewed, source-bound and freshly qualified.

## Runtime evidence and scope

Retained native CI artifacts establish JIT and AOT oracle execution of all twelve fixtures that had added residuals in the earlier census, including the seven numeric complex-union fixtures, complex-copy, Decimal and the optional tuple storage target. The successful synthetic CI checkout has the exact b0 production tree; an explicit final source-equivalence receipt binds its compiler/runtime/corpus to the proof-only final repairs. These are reused executions under verified source equality, not newly claimed runs. The complex-null fixture uses a handwritten TypeError deviation oracle, not a CPython parity claim.

This qualification concerns bounded models and the recorded Linux/Python/toolchain configuration. Python adapters, typed inventory export and runtime contracts remain trust boundaries. It is not a proof of all compiler/runtime behavior or a waiver of any rejected/unsupported obligation. Final publication also requires the parent's live release-head/base and integrated-CI checks and the independent final acceptance receipt.

The JSON companion binds every final record/report/acceptance/delta, the exact final snapshot-count binding, all source trees and review receipts by path, size and SHA256. The independent final acceptance will separately bind this completed disposition.
