# Alpha.1 Lean qualification

Source: `41cc2dde4705efcf03d9d910455ac72fd5da2312`; Python 3.13.16; Lean 4.35.0; Linux.

PASS: full report and current-input status both exited 0. Independent acceptance asserts that exactly 2,529 unique records equal the complete current corpus, every required check result is present (including the exact promoting-int selection), no inspection/check failed, inputs remain clean and byte-identified, actual checker executable hashes match, completion metadata matches the full census, and the isolated worktree is clean.

The 2,505-program report at `8350a073aab7` is historical comparison evidence only: it predates clean-input metadata hardening. All its programs remain present, with 24 additions and no newly unproved verdicts on shared programs. Coverage is bounded and is not unchanged.

## Coverage changes

Eight shared context-manager consumers lost a net 100 modeled field-initialization obligations when `func` backing storage became compiler-hidden ` _func`; new hidden factory bookkeeping is likewise outside this model. `check_lean_fields.unchecked()` includes non-space-prefixed fields, the class word, and three exception headers, but excludes other compiler-hidden fields. This is an explicit coverage reduction, not a claim that those runtime fields disappeared or are proved initialized. Existing README/GUARDS prose and the generated count report do not spell out this exclusion sufficiently; qualification must retain this disclosure. A nullable-specialization change in `json_decoder_override` adds 11 proved field obligations, for a net shared-corpus change of -89. The 24 new programs add 318 proved field obligations.

| Shared program | Field obligations before | After |
|---|---:|---:|
| `tests/programs/classes/contextmanager_receiver_class.py` | 10 | 8 |
| `tests/programs/classes/contextmanager_receiver_names.py` | 76 | 63 |
| `tests/programs/classes/contextmanager_super_module.py` | 54 | 46 |
| `tests/programs/classes/contextmanager_super_module_nested.py` | 23 | 19 |
| `tests/programs/classes/contextmanager_template.py` | 24 | 20 |
| `tests/programs/generators/gen_cm_gc.py` | 22 | 20 |
| `tests/programs/library/json_decoder_override.py` | 24 | 35 |
| `tests/programs/library/lib_contextlib.py` | 254 | 214 |
| `tests/programs/upstream/upstream_contextlib.py` | 302 | 275 |

Removed-null-check obligations decrease by 11 across four shared programs and increase by 31 across four others (net +20); every changed obligation is proved. Explicit class calls now preserve nullable receivers rather than treating them as non-null, so fewer eliminated checks in some callers and additional guarded specializations elsewhere change the obligation inventory. This does not relax the checker.

| Shared program | Null-removal obligations before | After |
|---|---:|---:|
| `tests/programs/classes/class_call_method.py` | 3 | 1 |
| `tests/programs/classes/contextmanager_super_module_nested.py` | 4 | 7 |
| `tests/programs/classes/inheritance_bound_identity.py` | 16 | 10 |
| `tests/programs/classes/inheritance_call_order.py` | 3 | 4 |
| `tests/programs/classes/inheritance_dispatch.py` | 16 | 14 |
| `tests/programs/exceptions/exc_super_imported.py` | 5 | 13 |
| `tests/programs/library/json_decoder_override.py` | 3 | 2 |
| `tests/programs/library/lib_contextlib.py` | 69 | 88 |

The new `contextmanager_python_int_args.py` program proves all seven modeled storage obligations, but two FUNCTIONS (`@c.0.1` and the context-manager `_recreate_cm` specialization) are unsupported because their tuple view has an unknown source representation. Their obligation counts are unknown; these are not two failed obligations. No runtime correctness failure is implied by that model limit. The remaining new programs add no unproved verdicts.

## Completion history

The first concurrent four-worker attempt was stopped with exit 130 after two SIGKILL inspection failures (468 records). None of its records were reused. A fresh isolated four-worker attempt completed 1,674 successful records, then its worker pool terminated abruptly; no recorded inspection/check failed. The documented `--resume` path accepted a byte-identical copy of those 1,674 successful records only after checking identical clean source/checker/corpus, actual checker hashes, Python/platform and full inventory. Two workers completed the remaining 855 programs. Both original failure archives are preserved unchanged. The final report is a complete same-source census, not a partial report.

## Evidence

- `alpha1-lean-report.md`: generated full report.
- `alpha1-lean-records.jsonl`: all 2,529 actual program records.
- `alpha1-lean-full-acceptance.json` and `.log`: independent full-corpus and identity assertions.
- `alpha1-lean-status.json` and `alpha1-lean.log`: successful command/status evidence.
- `alpha1-lean-history-comparison.json`: detailed old/new per-program coverage changes.
- `lean-alpha1-failed-concurrent/` and `lean-alpha1-failed-isolated4/`: preserved unsuccessful attempts.

Report SHA-256: `b8c850d11a7867589b42ce0f4de9bbd63d16220858370859c1b27d13b5932447`.
Records SHA-256: `db139c135eacbb0720243aad936b11edb5a13e42f6ef01428c25f1962c6ed345`.
