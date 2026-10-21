# Minimal compiler state contracts: research prototype

Refs [#767](https://github.com/den-run-ai/pystachy/issues/767),
[#801](https://github.com/den-run-ai/pystachy/issues/801) and
[#816](https://github.com/den-run-ai/pystachy/pull/816).
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
| `Frame` | AST check of initialization, exact save/restore mappings, constructor wiring, duplicate and missing fields, unconditional transfers | Whether a new `Gen` field omitted from every Frame list should have been function-scoped |
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

## Evidence at main c5d7f9e8

Baseline: [`c5d7f9e8ee334efedd4ff069cd052b4ba582ac85`](https://github.com/den-run-ai/pystachy/commit/c5d7f9e8ee334efedd4ff069cd052b4ba582ac85),
2026-10-21. AST inventory: **252 initialized Gen fields; 40 Frame fields**.
The earlier issue's field counts are historical.

| Input | Observed result |
|---|---|
| `global_inference.py` | Two passes. First aborts with `xs: list[int]` and decline `A.__eq__`; final pass has `xs: list[str]`, and keeps `B.__eq__` eligible. CPython 3.12.14 prints `True`. |
| `dry_template.py` | One successful dry call retains changes to `called`, `carried`, `compiled`, `fns`, `funcs`, `n`, `retainers`, `template_instances`, `template_retained`; saved emission is restored. |
| Existing `dynany_eq_template.py` | Four passes and eight successful dry calls; those calls retain register numbering (`n`). |

Each of these three inputs emits byte-identical hosted LLVM IR with and without
the observer, compared in separate fresh processes. This measures observer
transparency, not native execution, full-corpus parity or allocation neutrality
of a future refactor. Raw observations and input/source hashes are in
[`results.json`](results.json).

Local: Linux x86-64, CPython 3.12.14 (supported bootstrap interpreter).
**22 unit tests passed**, including controls that deliberately break constructor
initialization, field membership, transfer mappings, dry restoration, and each of
the five global rewinds. The controls also detect same-size dictionary/list
changes, nested function-record changes and alias replacement.
Ruff 0.17.0, four workflow-limit tests and `git diff --check` also pass.

Run from the repository root:

```sh
python3 tools/compiler_state_contract.py
python3 -m unittest discover -s tools -p 'test_compiler_state*.py'
python3 tools/compiler_state_probe.py research/compiler-state-767/dry_template.py
python3 tools/compiler_state_probe.py research/compiler-state-767/global_inference.py
python3 tools/compiler_state_probe.py research/compiler-state-767/global_inference.py --baseline
```

The tests are registered in Lint. Local `tools/setup.sh --check` fails because
Clang/LLVM is unavailable; full `make lint`, native build/JIT/AOT, `make verify`,
`make irsame` and GC stress were not run locally. The pinned recording interpreter
is 3.13.16; these standalone research fixtures add no corpus recordings. No claim
is made here about native Pystachy output for the new fixture. CI evidence belongs
to the PR's exact head and is reported separately there.

## Small follow-up changes, in order

1. **Review an explicit ownership inventory.** Classify newly added `Gen` fields
   as function context, transient traversal, persistent program discovery or
   pass output. Inventory mutable module globals separately: restart, loader
   initialization, configuration or immutable table. Require a reason for every
   exception. The current checker intentionally does not guess these categories.
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
