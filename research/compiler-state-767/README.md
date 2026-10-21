# Minimal compiler state contracts: research prototype

Refs [#767](https://github.com/den-run-ai/pystachy/issues/767),
[#801](https://github.com/den-run-ai/pystachy/issues/801),
[#816](https://github.com/den-run-ai/pystachy/pull/816) and
[#822](https://github.com/den-run-ai/pystachy/issues/822).
Draft proposal; partial acceptance only. No compiler/runtime source changes.

## Recommendation

Keep the fresh-`Gen` restart on speculative failure. First make the existing
boundaries executable contracts; consolidate their ownership only after observing
them. Do not resume compilation after an error using a partial snapshot.

The abandoned #816 prototype demonstrated why: a failed comparison refined a
global empty list to `list[int]`. Continuing in that state wrongly declined a
later valid method. Its green CI and corpus IR parity did not prove isolation.
The [recorded finding](https://github.com/den-run-ai/pystachy/pull/816#issuecomment-6313846369)
is historical evidence; this branch independently checks the current hosted
compiler's restart and decline decisions.

## Implemented slice

| Mechanism | Prototype contract | What remains unproven |
|---|---|---|
| `Frame` | AST check of direct, valued initialization in both Gen and Frame, exact save/restore mappings, constructor wiring, duplicate and missing fields, unconditional transfers | Whether a new `Gen` field omitted from every Frame list should have been function-scoped |
| Successful `dry()` | Original block, block list, loop list, cursor, terminator, line and `drying` restored, including identity and nested contents | Which other effects are semantically safe to retain across every input |
| Retained state | Hosted observer records changes throughout `Gen`'s reachable objects; catches same-key changes, aliases and nested changes | No whitelist of safe semantic effects; observations are not rollback approval |
| Failed compilation | Real driver's `Rejoin` path uses a fresh `Gen`, carries hints/declines, rewinds the five known globals | Exhaustive discovery of all mutable process globals or reentrant compiler services |

`Frame` stores references for nested compilation. It is not a transaction or a
deep copy. `dry()` suppresses temporary expression emission, but deliberately
retains semantic discoveries. Its exception path abandons the pass; it makes no
promise to restore an object that will be discarded. The observer rethrows every
exception and never continues that pass.

The hosted `Snapshot` supports primitives, lists, tuples, dictionaries and
compiler records. It preserves graph identity, aliases, cycles, dictionary order
and nested values, keeps old objects alive to prevent identity reuse, and rejects
unknown types. It is expensive debug tooling, unsuitable for the self-hosted hot
path. Deep graphs can hit Python's recursion limit. Use one small case per process.

## Evidence at main 0536d1a8

Baseline: [`0536d1a8e009ed59fb6485dd09f2fdd4661bd68a`](https://github.com/den-run-ai/pystachy/commit/0536d1a8e009ed59fb6485dd09f2fdd4661bd68a),
2026-10-21. AST inventory: **252 initialized Gen fields; 40 Frame fields**.
The earlier issue's field counts are historical.

| Input | Observed result |
|---|---|
| `tests/programs/inference/dynany_eq_restart_global.py` | Two passes. First aborts with `xs: list[int]` and decline `A.__eq__`; final pass has `xs: list[str]`, and keeps `B.__eq__` eligible. CPython 3.13.16 prints `True`. |
| `dry_template.py` | One successful dry call retains changes to `called`, `carried`, `compiled`, `fns`, `funcs`, `n`, `retainers`, `template_instances`, `template_retained`; saved emission is restored. |
| Existing `dynany_eq_template.py` | Four passes and eight successful dry calls; those calls retain register numbering (`n`). |

Each of these three inputs emits byte-identical hosted LLVM IR with and without
the observer, compared in separate fresh processes. This measures observer
transparency, not native execution, full-corpus parity or allocation neutrality
of a future refactor. Raw observations and input/source hashes are in
[`results.json`](results.json).

Local: Linux x86-64, CPython 3.13.16 (the pinned recording interpreter).
**31 unit tests passed**, including controls that deliberately break constructor
initialization (including annotation-only and conditional Gen assignments), field
membership, transfer mappings, dry restoration, and each of
the five global rewinds. The controls also detect same-size dictionary/list
changes, nested function-record changes and alias replacement.
Ruff 0.17.0, mypy 2.4.0 (45 compiler source files), four workflow-limit tests and
`git diff --check` also pass. Main's #820 type-checking changes were merged into
the branch; the documentation conflict was resolved by retaining both its
type-checking guidance and these research controls. Both Lint steps remain.

Run from the repository root:

```sh
python3 tools/compiler_state_contract.py
python3 -m unittest discover -s tools -p 'test_compiler_state*.py'
python3 tools/compiler_state_probe.py research/compiler-state-767/dry_template.py
python3 tools/compiler_state_probe.py tests/programs/inference/dynany_eq_restart_global.py
python3 tools/compiler_state_probe.py tests/programs/inference/dynany_eq_restart_global.py --baseline
```

The unit tests are registered in Lint. The global-inference fixture now lives in
`tests/programs/inference/dynany_eq_restart_global.py`, with its adjacent `.out`
recorded using `PYTHON=python3.13 tests/record.sh` under CPython 3.13.16. The normal
corpus discovery includes it in native JIT/AOT and GC configurations. Its hosted
probe continues to use the same file; there is no duplicate research copy.

The checker review at `572bb658` found that the Gen initialization scan counted
annotations without values and assignments under `if False`. Both false positives
were reproduced before the fix. Only direct assignments with values now satisfy
the declared Frame contract; the three new negative controls cover both Gen cases
and an annotation-only Frame field.

Local `tools/setup.sh --check` still fails because Clang/LLVM is unavailable.
`tools/setup.sh --minimal` could not install it: apt's permission setup failed
(`setgroups`/`setegid`/`seteuid`, HTTPS method exit 112). No sandbox settings were
changed. Full `make lint`, native build/JIT/AOT, `make verify`, full-corpus
`make irsame` and GC stress were not run locally. New-head CI execution evidence
is reported separately in the PR; corpus registration alone is not a passing run.

### Native evidence for the review fixes

At `c8a7f326`, all 32 applicable checks passed; the fork-only DCO check skipped.
The #816 fixture is explicitly listed in the successful native JIT/AOT, GC JIT
and GC AOT case manifests. Those shards respectively report 2,621/2,621,
1,813/1,813 and 1,208/1,208 passed; GC tests collect at every program allocation.
The differential expectation is `True` followed by exit status zero.
The tested clean merge `cceb7652` has parents main `c5d7f9e8` and PR head
`c8a7f326`. [Artifact hashes, manifests and job links](ci-c8a7f326.json) preserve
this evidence. This is historical validation of that head, not later additions.

## Nested compilation follow-up (#822)

[#819](https://github.com/den-run-ai/pystachy/pull/819) adds the broader field
inventory, including `gen_enter` and fields omitted from every Frame list.
[#824](https://github.com/den-run-ai/pystachy/pull/824), reviewed here at
`59713c2c`, applies the eight operation-field fixes found by that audit.
Keep those production changes in their existing PR. This prototype adds a
dynamic boundary check and an acceptance control; it does not implement another
compiler fix or import either branch.

The boundary probe calls the actual `Gen.save`, `Gen.enter` and `Gen.restore`
with deliberately non-neutral operation state at nesting depths 1, 2 and 3.
It checks neutral callee entry and restoration of the caller's values and object
identities for `drying`, `carried`, `nonecmp`, `fieldcmp`, `cmpnode`, `stkkey`,
`reflcopies` and `stmtexpr`. These synthetic boundary checks complement actual
program regressions; they do not prove that every caller uses the boundary or
that retained semantic discoveries are safe. They require no rollback or new
production reflection.

[Pinned results](nested-results.json): main `0536d1a8` reports all eight entry
leaks and all eight caller restoration changes at every measured boundary;
#824 `59713c2c` reports none. `--strict` exits 1 and 0 respectively. The normal
invocation prints findings without failing, so the research probe can inspect
the known-broken baseline. The six new mechanism tests check existing saved
fields, deliberate entry/restore defects, missing attributes, equal-value object
replacement and in-place mutation. All **31 state tests pass** on the prototype
and when its tools are overlaid on #824; they do not bless main's known leaks.

```sh
python3 tools/compiler_state_nested_probe.py
python3 tools/compiler_state_nested_probe.py --strict  # expected exit 1 on this branch
```

The original dry observer also passes against #824. In `dry_template.py`,
`carried` is no longer among the retained changes. Other program discoveries
remain observable; a successful boundary check does not approve those effects.

### Preserve accepted programs too

`tests/programs/optional/nestcomp_nonecmp_one_read.py` is the one-iteration
acceptance control for #822's `nonecmp` reproducer. Its only truth test reads
`None`, before the later assignment; CPython prints `x is None`, `y is falsy`
and `x still None`. Main (both `c5d7f9e8` and `0536d1a8`) compiles it successfully
with typed-IR checks enabled.
The emitted IR takes the falsy branch in its only iteration. #824 at
`59713c2c` rejects it with the cannot-infer-None diagnostic.
[The pinned hosted comparison](nonecmp-acceptance.json) records both results,
input/recording hashes and CPython 3.13.16 output. Native execution of this new
control remains for CI; it is registered in the differential corpus and its
`.out` was generated with `tests/record.sh`.

The #824 description acknowledges this class of new rejection. It conflicts
with the repository's rule to preserve previously accepted programs that match
CPython, even when the prior implementation got the right result accidentally.
Fixing the multiple-iteration wrong result must also preserve this boundary.
Retaining the leaked flag or broadly permitting unresolved `NONEVAR` reads is
not a demonstrated safe solution. Further optional inference work is required.

At the reviewed #824 head, CI also timed out its
[`gc-self` job](https://github.com/den-run-ai/pystachy/actions/runs/39630216342/job/119327947645)
after 600 seconds (exit 124), which failed aggregate verification. That establishes
a failed gate, not its cause. Both acceptance and verification remain open before
that change is ready to merge.

## Small follow-up changes, in order

1. **Review an explicit ownership inventory.** Classify newly added `Gen` fields
   as function context, transient traversal, persistent program discovery or
   pass output. Inventory mutable module globals separately: restart, loader
   initialization, configuration or immutable table. Require a reason for every
   exception. #819 supplies the Gen-field inventory; module-global classification
   remains pending. Preserve the existing negative control for a missing
   `return fr` when consolidating its checker with this prototype.
2. **Give restart state one owner.** Introduce a small subset-compatible restart
   record for `FILES`, `LAMBDAS`, `RENAMED`, `LIBS`, `LINKDL`, retaining current
   truncate/reset semantics and alias identity. Distinguish driver-entry state
   from loader-owned resets. Extend controls for repeated compilations and
   success/error/restart combinations before claiming per-compilation isolation.
3. **Extract one context only when it simplifies ownership.** Start with the
   already-declared function frame, or generate its explicit transfers from a
   reviewed schema using a host tool. Keep direct subset-compatible assignments;
   do not introduce runtime `getattr`, reflection or a general deep-copy engine.
   Require compiler/runtime fixed points, `make irsame REF=<base-sha>`, full
   verification and no increase in stressed self-compilation allocations or
   collections before adoption.

Before batching could be reconsidered, every semantic mutation reachable through
globals, `FnInfo`, `ClassInfo`, specialization/dispatch registries and aliases must
have a proven commit/discard owner. Append-only growth is not automatically safe:
new entries can change which later code is compiled. Size comparisons, a larger
allowlist, or a finite passing probe suite cannot establish that guarantee.

This prototype therefore adds observability and drift checks at zero production
compiler-code cost. It proposes no compilation speedup, no replacement for the
single AST walk, and no change to the unrelated union-guard proof gap in #768.
