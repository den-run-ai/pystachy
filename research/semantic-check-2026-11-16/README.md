# Semantic `pystachy check`: validation record

This record validates the change that makes `pystachy check` compile through
finalization, recover unit by unit, report typing, layout and specialization decisions
separately, and freeze those decisions after discovery. The change is commit `5dbfa130`
on top of `bb04e196` (#1499 merged into v0.5.0-alpha.4); until it is published on its own
branch, [a bundle](bundle/check-semantic.bundle) keeps it: `git fetch
research/semantic-check-2026-11-16/bundle/check-semantic.bundle check-semantic-bundle`
restores that exact commit in a clone that has `bb04e196`. Every result applies to the
compiler built from that commit. The reference
compiler is `bb04e196`'s native build (`./pystachy` before the change, SHA-256 prefix
`41338c893f247d68`). The final build of the change has SHA-256 prefix `07c728b01160e1d6`.

Local runs on November 16, 2026 used 4 x86-64 cores, Ubuntu clang and LLVM 18.1.3,
CPython 3.13.18 (`.python-version` pins 3.13.16) and Lean 4.35.0.

## Results

| Check | Result | Record |
|---|---|---|
| Bootstrap | `make` reached fixed points: compiler IR 968,315 lines (961,586 before), `runtime.py` IR 21,214 lines (unchanged). The binary grew from 7,098,168 to 7,145,920 bytes (+0.67%). | [make](results/make.log) |
| Ordinary compilation unchanged | `tools/irsame.sh` against `bb04e196`, one shared `PYSTACHY_HOME` (`lib/` and the runtime are unchanged): all 4,796 corpus programs have identical IR, diagnostics and exit status. | [log](results/irsame-ir.log) |
| `check` agrees with `ir` | `tools/irsame.sh --semantic ./pystachy ./pystachy`: on all 4,796 programs, `check` accepts exactly what `ir` compiles, silently, and rejects the rest with `ir`'s message as its first line and the same exit status. | [log](results/irsame-semantic.log) |
| No invented errors | The mutation harness injected a type error at the top of one function, and of two functions, of each corpus program: 3,229 mutants of 1,760 programs. No `check` error was reported outside an injected line; every first line equals `ir`'s. Both errors were reported as errors in 966 of 1,469 two-site mutants; in the rest the second is a note. | [summary](results/mutate.log), [data](results/mutations.json.gz) |
| Cost | Seven interleaved pairs on one pinned core, the same compiler: compiling `pystachy.py` itself, `check` took 4.791 s and 833 MiB against `ir`'s 5.478 s and 976 MiB; `raytrace.py` 29 against 31 ms. | [cost](results/check-cost.json) |
| Hosted tests | `make check-fast lint` ran 44 unittest invocations with 1,246 tests; its one skip, the real-LLVM retained-IR test, passed separately. The check command (13), pipeline (13, with the decision freeze), Lean pipeline (21), frame fields (18), cache (33), inspection (34), compiler-state (138) and bootstrap-tier (8) tests also passed on their own. | [check-fast](results/check-fast-lint.log), [steps](results/hosted-tests.log) |
| Lean | `lake build` completed; the axiom audit passed for 62 theorems, including `discovery_may_decide`, `consumers_cannot_decide` and `discovered_cannot_decide`. The model matches `PipelineState` on all 221 reachable transitions, decisions included. | [audit](results/lean-audit.log) |

## Method

`scripts/mutate_check.py` parses each `tests/programs/*/*.py` program without a `.path`
with CPython, and inserts `pys_bad_injected = 1 + "injected"` before the first statement
(after a docstring) of the first top-level function or method. A second mutant does the
same in the last one too. A mutant is kept only if CPython places each injected line in
that function's body. It runs `ir` and `check` on each mutant and requires every `error:`
line of `check` to name an injected line. Notes may name any line.

The harness found two kinds of invented errors before the final rules, which the change
fixes ([before](results/mutate-before-store-taint.log)):

- A special method left out returns nothing, and `gen_instance` checked its return type in
  the caller (`__lt__ must return bool`). A body left out now skips that check.
- The compiler infers the type of a global, an empty container or a field first assigned
  `None` by compiling the functions that set or fill it (`early`, `none_field`). Leaving
  such a body out left the type unknown. Leaving out a body that assigns a global or a
  field, or fills a container it did not make, now taints the rest of the attempt.
  Constructors' own field stores do not: the class declaration types them from the
  source. That exemption raised the two-error recall from 757 to 947 of 1,469 mutants
  ([before](results/mutate-before-constructor-refinement.log)).

`scripts/check_cost.py` runs `ir PROGRAM -o /dev/null` and `check PROGRAM` alternately with
`taskset -c 3`, after one warm-up run each, and reads peak RSS from `wait4`.

## Limits

Module code is one unit: its first failure stops checking. A body that writes a global
or a field taints every later failure, which then becomes a note even when it is
independent. The mutation harness injects simple type errors at the top of a function;
it does not show that every kind of failure is isolated soundly. CI runs the hosted
`tools/test_check_command.py` tests, not the corpus comparisons above.

Prepared with Claude Code.
