# Manual classification of the final match IR comparison

**All 31 differences are expected feature/rejection-boundary changes. No blocker, newly rejected previously accepted input, or accepted-to-accepted IR difference was found.**

Base `b40ee875bf72b86804c4f5a300066f4f7c3eb20b`; candidate `dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6`; candidate tree `0e4c2682f25b0555cac052fa36830ed567c3fa1e`.

The completed oracle compared **4,438 inputs: 4,407 identical, 31 differing**. The reviewer read every saved difference and checked its source and declared rejection where applicable. Inventory and completed timing rows contain exactly the same 4,438 unique cases. No compiler, native executable or backend was launched for this review.

| Classification | Count | Exit status |
|---|---:|---|
| Newly supported bounded-match programs: 14 regressions plus benchmark and example | 16 | 1 → 0, explicitly logged |
| More specific bounded-match rejection diagnostics | 13 | 1 → 1 |
| Imported decorated special method reaches an existing rejection | 1 | 1 → 1 |
| Existing KDE rejection advances to incompatible lambda storage | 1 | 1 → 1 |
| Previously accepted inputs newly rejected | 0 | No 0 → nonzero transition |

The oracle reports every unequal exit-status pair. All sixteen logged transitions are `1 -> 0`. For the fifteen diagnostics-only changes, statuses are equal; both diagnostics use the unchanged `diagnostics.fail()` path ending in `sys.exit(1)`. Individual equal numeric statuses are not persisted by the oracle, so their `1 -> 1` attribution combines the saved comparison with that source proof. The 4,407 identical inputs include successful compilations and rejection fixtures; they are not a count of successful programs.

IR bytes and statuses are compared exactly. The existing oracle narrowly normalizes library source locations in diagnostics; this run introduces no additional normalization and changes only its displayed-difference cap. The overall exit status is 1 because differences exist, not because the comparison was incomplete.

## Every newly accepted case

| Case | Reviewed reason |
|---|---|
| `tests/programs/apps/match_dispatch_workloads.py` | Application consumer imports the new tuple/dataclass command dispatcher and independently checks match/if benchmark results. |
| `tests/programs/generators/gen_match_dispatch.py` | Fixed-tuple patterns, literal OR and guards inside a generator; subject effects, yield and close/finally paths. |
| `tests/programs/inference/dynany_match_literals.py` | Dynamic Any singleton/literal/capture matching plus a known concrete dataclass mismatch. |
| `tests/programs/inference/dynany_match_python_int.py` | Dynamic Any literal/capture matching with promoting integers, bool identity and float/integer equality. |
| `tests/programs/language/match_binding.py` | Captures before false guards, closure visibility, unbound locals, private names and loop control. |
| `tests/programs/language/match_capture_staging.py` | Partial-pattern failures, OR/as/nested patterns, callback visibility, nonlocal/closure captures and alias retention. |
| `tests/programs/language/match_condition_order.py` | Equality and guard-truthiness order, false-guard captures, OR staging and guard analysis after union rebinding. |
| `tests/programs/language/match_dataclasses.py` | Plain dataclass fields, keyword-only/match_args options, preloaded fields under callback mutation and scalar mismatch. |
| `tests/programs/language/match_exceptions.py` | Exceptions during pattern/guard evaluation and preservation of old or committed local/global bindings. |
| `tests/programs/language/match_large_hex.py` | Positive and negative huge hexadecimal integer literals with e digits, plus a no-match control. |
| `tests/programs/language/match_literals.py` | One subject evaluation, case order, literals/singletons, guards and capture without invoking object truthiness. |
| `tests/programs/language/match_nested_dataclasses.py` | Empty/nested plain dataclass patterns with nullable concrete dataclass values. |
| `tests/programs/language/match_python_int.py` | Promoting-int scalar sequence mismatch, huge literals, tuple OR/guard and concrete dataclass captures. |
| `tests/programs/language/match_tuples.py` | Fixed tuple length tests, OR/as/captures, nested tuples, guards and scalar sequence mismatch. |
| `bench/match_dispatch/workload.py` | New focused consumer uses scalar OR routing, fixed tuples and concrete dataclasses with captures/guards and known-answer checks. |
| `examples/match_dispatch/dispatch.py` | New end-to-end command consumer uses fixed-tuple parsing and concrete dataclass dispatch with bounded literals, alternatives and guards. |

All sixteen are new files in the candidate tree. Each loses exactly the old unsupported-match diagnostic, exits successfully and produces IR only with the candidate. These results establish acceptance, while separate native/GC-stress tests establish execution behavior.

## Every changed rejection

| Case | Reviewed reason |
|---|---|
| `tests/errors/language/match_boolean_optional_union.py` | Boolean singleton matching on a union that can contain bool/int/None requires unsupported representation dispatch; explicit rejection is the documented boundary. |
| `tests/errors/language/match_dataclass_any.py` | A dynamic Any subject requires class-tag dispatch; reject before folding its storage type to a mismatch. |
| `tests/errors/language/match_dataclass_any_field.py` | A nested dynamic Any field has the same unsupported class-dispatch requirement as a top-level Any subject. |
| `tests/errors/language/match_dataclass_args_inherited.py` | Inherited dataclass hierarchy and custom __match_args__ are explicitly outside the concrete plain-dataclass contract. |
| `tests/errors/language/match_dataclass_args_method.py` | A method named __match_args__ is custom class metadata and must not be treated as generated dataclass fields. |
| `tests/errors/language/match_dataclass_args_qualified_method.py` | Imported qualified class with custom __match_args__ method reaches the same bounded class-pattern rejection. |
| `tests/errors/language/match_dataclass_args_qualified_property.py` | Lowering exposes an existing imported-class restriction: special method __match_args__ has a decorator. The property is unsupported and is not executed. |
| `tests/errors/language/match_dataclass_duplicate.py` | The positional first field and explicit x keyword select the same field; duplicate subpatterns are rejected. |
| `tests/errors/language/match_dataclass_keyword_only.py` | The keyword-only y field is absent from generated positional __match_args__; two positional subpatterns exceed its one field. |
| `tests/errors/language/match_dataclass_no_args.py` | match_args=False provides no positional fields, so the single positional subpattern is invalid. |
| `tests/errors/language/match_dataclass_union.py` | A union of two dataclass types requires unsupported runtime class dispatch; reject instead of silently folding false. |
| `tests/errors/language/match_list_subject.py` | A list subject requires general-sequence matching, outside the fixed-tuple contract. |
| `tests/errors/language/match_plain_class.py` | An arbitrary non-dataclass class pattern is outside the supported concrete dataclass contract. |
| `tests/errors/language/match_shadow_class.py` | A local integer parameter shadows the dataclass name; the pattern target is not a statically known dataclass. |
| `tests/errors/library/lib_statistics_kde.py` | Existing KDE kernel-selection literals now lower. Different branch lambdas then meet the unchanged one-function-type-per-slot restriction; KDE remains unsupported. |

Every new diagnostic matches its fixture's `# error:` expectation. Fourteen changed rejections are new negative fixtures. The remaining case, `lib_statistics_kde.py`, already existed and remains rejected: its scalar kernel match now lowers, exposing the existing requirement that a function-valued slot hold one function type. Its longer diagnostic retains absolute library paths because the existing normalizer conservatively leaves its prose unchanged; this is not an unexplained IR/path difference.

## Unchanged controls and limits

- `tests/errors/syntax/syntax_match_duplicate_key_over_limit.py` occurs once in the input inventory and completed timings and is absent from the complete difference list. Its source is identical in base and candidate. The two Pystachy compilers therefore compare identically; the documented CPython decimal-conversion-limit discrepancy predates this work and persists. `match-syntax-baseline.json` retains that separate source/history evidence.
- `tests/errors/language/match_dataclass_args_property.py`, the fifteenth new negative fixture, also compares identically. Both compilers encounter the existing direct special-method decorator rejection before lowering its match.
- No retained diff contains a comparison between two differing accepted IR files. Every emitted-IR difference is a newly accepted program. This is compilation/diagnostic evidence; execution correctness and timings are separate qualifications.

The companion `match-irsame-classification.json` contains all 31 exact old/new diagnostics, source hashes, log locations, status evidence, and hashes of the reports reviewed. The original full log and machine report remain unchanged.
