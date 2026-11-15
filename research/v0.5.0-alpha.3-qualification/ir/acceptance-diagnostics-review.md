# Alpha.3 acceptance and diagnostic review

**No actionable blocker found in these 183 cases.**

Candidate `b0bda81ec2b9954c3c5e0f658c051439126a5c22` versus alpha.2 `80490143498d149d407343ba1cb7aedb1db2d2c5`.

This review covers all 121 rejected-to-accepted inputs and all 62 changed rejected-to-rejected diagnostics in the retained 4,771-case scan. It does not claim runtime or Lean qualification.

## Findings and evidence boundaries

- All 62 changed error cases retain exit 1, one complete expected diagnostic, and no emitted LLVM file.
- No tests/errors case becomes accepted. New acceptance does not alone establish runtime correctness or a Lean proof.
- The 121 statuses concern current input bytes: 120 added fixtures and one changed pre-existing fixture; original alpha.2 input compatibility is independently checked by the other reviewer.
- Complex default cases pass explicit valid arguments; companion omitted-default cases remain rejected.
- Unused invalid constructor descendants stay lazy; the demanded invalid descendant still rejects for its missing field.
- Complex union None deviation has an explicit retained null test and runtime raise; literal identity deviation is already documented.
- Path-only descriptions require byte-identical referenced libraries. datetime is separately comment-only; enum and statistics receive explicit changed-library explanations.
- statistics changed its Decimal import to a CPython-only guard; nine +3-line diagnostic moves preserve byte-identical rejecting functions. NormalDist remains rejected at the next unsupported method.

## Disposition counts

| Category | Cases |
|---|---:|
| comparison_decline | 20 |
| complex_boundary | 14 |
| complex_default_boundary | 2 |
| complex_default_laziness | 2 |
| complex_dynamic | 11 |
| complex_typed | 33 |
| constructor_boundary | 3 |
| constructor_specialization | 18 |
| datetime_comment_only_library | 2 |
| decimal_boundary | 4 |
| decimal_subset | 10 |
| decline_boundary | 6 |
| documented_deviation | 2 |
| enum_missing_result_guard_unchanged | 1 |
| extended_existing_fixture | 1 |
| generic_type_reflection | 3 |
| identity_union_keys | 4 |
| key_type_boundary | 8 |
| none_optional_keys | 5 |
| normaldist_rejection_order | 1 |
| numeric_protocols | 6 |
| numeric_result_boundary | 2 |
| promoting_optional_tuple_keys | 1 |
| provisional_none | 2 |
| runtime_tuple_keys | 3 |
| statistics_preserved_rejection_and_import_boundary | 9 |
| unchanged_library_home_path | 10 |

## Per-case record

`acceptance-diagnostic-review.json` contains every input path, unique case explanation, complete old/new diagnostics, input/sidecar/raw-evidence hashes, expected-message checks, baseline-input relationship and the relevant library/function correspondence. The plural filename is a byte-identical alias for the parent’s requested path.

The raw evidence remains in `ir-audit/cases/INDEX`. No normalizer, source, compiler or prior evidence was modified. No heavy execution was started.
