# Alpha.2 qualification stopped at a validation blocker

Final snapshot: 2026-11-09 06:45 UTC. This is research/validation evidence, not release-ready evidence. Keep this directory off main.

## Outcome and public state

- Merged [#1170](https://github.com/den-run-ai/pystachy/pull/1170) with an expected-head check after fresh current-main CI and Codex review. Main is `d6b9b3f18bc5adf0da021da46f74c9837be0c604`.
- [Full main CI](https://github.com/den-run-ai/pystachy/actions/runs/42571513169) passed: 68 successful jobs and two expected skips. Installation, Packages, Lint and Performance smoke also passed on that commit.
- [Draft #1187](https://github.com/den-run-ai/pystachy/pull/1187) preserves the fixes for #1183/#1184, VERSION and alpha.2 notes. Head: `52da3b8ffd394f124697dfaadb0d0e55108866a7`; tree: `0e84b32e17da9091f5d7dba9b36dcda1cea749f9`; base: the main commit above.
- [Candidate CI](https://github.com/den-run-ai/pystachy/actions/runs/42571593239) finished successfully with all 16 jobs passing, including the aggregate gate. Lint, Performance smoke and Submission format passed; DCO is an expected same-repository skip. Codex completed review of the exact head without findings; no review threads remain. These successes do not resolve the missing full local IR qualification.
- No alpha.2 tag was present at the stop snapshot. No release workflow, native/Docker publication or PyPI publication was started. The PR remains draft even if its remaining CI becomes green.

## Prepared changes

Import resolution now requires regular `.py` and `__init__.py` files, including the driver's ffi probes. Symlinks to regular files and later search paths remain supported; cache validation records candidate-kind transitions.

Invalid JIT-inline settings are rejected before cache locks or temporary launch files are allocated. Native compiler startup consumes inherited argv metadata only with the explicit JIT handoff. Tests cover cache hits/misses and ordinary AOT, ORC and MCJIT arguments.

Release notes state the remaining MCJIT descriptor and closed-stream/input-read differences. Optional I/O and numerical-worker stacks remain deferred. No compiler/GC/CI limit was relaxed.

## Successful local evidence and identity

The candidate native compiler reached three identical compiler IR stages (878,858 lines) and three identical runtime IR stages (19,907 lines). Focused hosted loader/cache/launch/exec tests passed. Native cache/import/launch probes passed 167 assertions across 50 launches with zero timeouts; descriptor/signal/embedding probes passed 55 hosted/native checks.

Baseline native SHA256: `cbdca38e5f5b522e5309a51f960f4ab1729a5e9f3e282845cd55c35794b22e93`, built from main `56678df4c667afb4c9b35d854e97cdc9f5c0c3f7`.

Candidate native SHA256: `60e7722082d992b556f6c4655dacbd9db8d54a43da8b02e116d5ce4ec0202a2b`. It was built from local `c37b38ee`; subsequent local commits only tightened release notes. Public head `52da3b8f` has identical compiler/runtime/probe sources; its complete tree matches the final local candidate. The local binary's ordinary source-build revision metadata is unknown; it is not a release archive.

Toolchain: Python 3.13.16; LLVM 18.1.3; Linux x86-64. These checks do not replace the supported-platform matrix or exact-release artifact qualification.

## Why release advancement stopped

The ordinary unchanged IR oracle completed 4,354 corpus cases but reported 264 differences. Its first three displayed differences are generated ImportError strings containing the separate compiler-library real paths. This matches existing [#527](https://github.com/den-run-ai/pystachy/issues/527); the ordinary output alone does not prove every difference has that cause.

Controlled replays retained separately copied compiler/runtime/library inputs at the same real home pathname, with no IR or diagnostic rewriting. Earlier attempts exposed unreliable process identity and directory/file restoration in this environment. None is counted as full qualification.

The final harness uses a permanent home, fresh-mtime writes, independent immutable binaries/snapshots, serial calls, and exact input-manifest checks before/after each invocation. Its five-case dry run, including the compiler itself and runtime mode, passed with an intact audit across a tool yield.

The full replay then failed its pairing guard after 59.029 seconds. The controller stopped only its owned process group; oracle exit was 130, final audit was not run, and `qualified` is false. A pending record for `class_constants.py` survived even though both calls for that case and 20 later pairs were already logged as complete. The controller observed 122 timing lines; a later read observed 119. There were 115 completed full-corpus compilation pairs logged before the failure, with no output/status differences, but that is incomplete evidence.

These observations indicate a validation-environment integrity problem. Stale filesystem synchronization is an inference; its exact mechanism is unproven. The records do not establish a compiler regression.

## Evidence files and limits

- `unrelocated-irsame.log`: actual unchanged-oracle failure and corpus count.
- `relocate.py`: final scratch harness; it is not a proposed product/oracle change.
- `dry-run.json` / `dry-audit.json`: successful bounded dry run.
- `full-run.json`: invalid full-run command, source/toolchain details and termination.
- `failure-summary.json`, `stale-pending.json`, `invocation-excerpt.json`: preserved conflicting state.
- `partial-times.txt`: incomplete timing records including failed harness calls; not performance evidence.
- `native-bootstrap.log`, `jitfdprobe.log`, `launch-before.json`, `launch-after.json`: focused local evidence.

All local validation processes and monitoring have stopped. GitHub CI was left intact and subsequently completed successfully; no jobs were canceled.

## Resume condition

Complete a byte-exact full corpus comparison, including diagnostics and exit statuses, in a reliable execution/filesystem environment while preserving each compiler's own inputs and accounting for #527. Then recheck the current PR head/base, all applicable CI and review threads before marking ready or merging. Only after the exact merged main commit passes its full publication gates should alpha.2 native/Docker and PyPI publication proceed.

Tracking work is recorded in [#1186](https://github.com/den-run-ai/pystachy/issues/1186) and the alpha.2, conditional alpha.3, v0.4.0 and Research milestones. #1154 was closed from already-merged acceptance evidence; #1183/#1184 remain open until the prepared fix is qualified and merged.
