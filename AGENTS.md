# Working on Pystachy

Shared instructions for Codex, Claude Code and other coding agents. `CLAUDE.md`
imports this file; keep project guidance here rather than maintaining two copies.
This is an onboarding guide, not a snapshot of open issues or CI status.

## Start with the current tree

1. Read the user's scope, `git status --short --branch`, `git remote -v`,
   `git worktree list` and recent commits. Preserve other sessions' uncommitted work.
   Fetch the target branch, record its SHA and use your own branch/worktree or clone.
2. Read the relevant issue, linked PRs, latest review threads and live PR metadata.
   Search for the same minimal failure before starting another implementation or issue.
   Old chat summaries, PR bodies and dated reports are leads, not current-state evidence.
3. Reproduce on current main and the proposed branch, against pinned CPython where
   applicable. Distinguish a regression, previously unsupported behavior, a documented
   deviation and a setup failure. Prioritize silent wrong results, crashes and memory
   safety before expanding support; fix the smallest coherent cause.
4. Identify overlapping work before editing shared compiler/runtime files. Agree on
   branch ownership, dependencies and who integrates/merges. Delegate independent
   investigations with explicit boundaries; review their evidence before using it.

| Need | Read first |
|---|---|
| Build/setup | [README](README.md), [installation](docs/install.md), `tools/setup.sh --check` |
| Locate compiler code | [source map](src/README.md), [internals](docs/internals.md) |
| Language/type contract | [language](docs/language.md), [typing](docs/language/typing.md), [deviations](docs/language/compatibility.md) |
| IR/runtime/FFI | [typed IR](docs/typed-ir.md), [subset runtime](docs/runtime-in-subset.md), [FFI](docs/ffi.md) |
| Tests and CI | [testing](docs/testing.md), `tests/verify.sh --list`, `.github/workflows/` |
| Library gaps and ports | [stdlib](docs/stdlib.md), [lib](lib/README.md), [ports](ports/README.md), [audit updates](docs/reports/compatibility-updates.md) |

Use `rg` and the source map to find the responsible layer. Use the available GitHub
connector/API or authenticated CLI; do not assume `gh`, browser access or a particular
session's tools exist. When access is missing, report the specific limitation.

## Build and test deliberately

- Bootstrap accepts Python 3.11+, but recordings and full verification use the
  version in [`.python-version`](.python-version). Check the actual interpreter;
  `make` uses `PY`, while `tests/record.sh` uses `PYTHON` (default `python3`).
  Development dependencies are in `tools/requirements-dev.txt`. Follow the setup
  guide for LLVM and UBSan; `PYSTACHY_LLVM` must point to a complete matching toolchain.
- `make` checks compiler **and runtime** IR fixed points. Rebuild after compiler or
  runtime changes, branch switches and integration. An existing `./pystachy`,
  `build/ref/` or `build/verify/` executable is not proof of which sources it contains.
  If reusing a verified binary, record its source identity separately from the checkout.
- When ad hoc probes disagree, inspect inherited `PYSTACHY_HOME`, `PYSTACHY_PATH`,
  cache, optimization and GC settings; full verification sanitizes coverage-changing
  options, but direct invocations may not. Keep probe inputs and environments explicit.
- Keep concurrent builds/verification groups in separate checkouts: `build/verify`
  and the report path are shared. Use `mktemp -d` for scratch probes; PID-only names
  can collide across sessions. Bound `PYSTACHY_JOBS` on shared hosts. Do not run
  timing benchmarks alongside heavy builds or broad test jobs.

Run commands from the repository root. Replace the example selectors with affected tests.

```sh
tools/setup.sh --check
make
make test FILES="tests/str_*.py tests/errors/rtmode_*.py"
make test-py FILES="tests/str_*.py tests/errors/rtmode_*.py"
make lint check-recordings
```

| Change/risk | Additional evidence |
|---|---|
| Compiler/runtime/library behavior | Complete `make verify` or its required CI matrix on the reviewed tree before declaring merge-ready; report missing/failed stages |
| GC, ownership, container layout | Focused JIT/AOT with `PYSTACHY_GC_STRESS_PROGRAM=1`; relevant `listprobe`, `dictprobe`, `eqprobe`, `fileprobe`; full GC groups |
| Lowering, effects, runtime ABI | `make check-ir check-runtime`; affected `tests/ir/*.calls`/effect contracts |
| Code-generation-preserving refactor | `make irsame REF=<base-sha>`; compare diagnostics/exit status as well as IR |
| FFI, embedding, extensions | `make test-ffi`; CPython twins and actual native calls, with alias/lifetime cases |
| Driver/runtime cache | `make test-cache`; invalidation and failure paths |
| Syntax/diagnostics | `python3.13 -I tools/syntax_sweep.py --compiler ./pystachy <paths>`; valid boundaries and rejection fixtures |
| Ports/performance | `make port-check` or affected port checks; relevant benchmark correctness target before timings |
| Docs only | Check links, commands and `git diff --check`; disclose that runtime suites were not rerun |

Start with the focused reproducer, then broaden for the affected risk and required gates.
`make test` covers JIT/AOT but is not the full `make verify` matrix. A hosted parse or
IR check without LLVM is not a native execution or bootstrap result. The authoritative
plan and coverage checks live in `tests/verify.sh` and `tools/merge_verification.py`;
do not duplicate a fixed job count here. Verification must prove expected counts,
source/toolchain identity and every required stage, not just a zero-failure excerpt.
If a stage times out and passes alone, report both outcomes; do not relabel the original
partial matrix as a complete pass. Do not disable gates to make a run green.

## Make regressions hard to hide

- Add a minimal independent regression that fails before the fix. Separate cases
  whose imports, helper calls or inferred types can mask one another. Exercise direct,
  qualified, aliased and quoted annotations when resolution is involved.
- Differential cases live in `tests/`; record `.out`/`.err` with
  `PYTHON=python3.13 tests/record.sh NAME` using the pinned interpreter, never by
  copying Pystachy's output or editing expectations to match a bug. Use `.path`
  for import setup. Rejections belong in `tests/errors/`; intentional deviations
  belong in `tests/deviations/` and the language docs. Move resolved deviations
  into the differential suite.
- Test positive behavior **and** rejection boundaries. For lifetime/GC fixes, use a
  targeted negative control where practical: removing the fix should expose the
  missing root, premature collection or stale read. A successful allocation loop
  alone is weak evidence of memory safety.
- The compiler must remain in its own supported Python subset. Follow the
  `gen_*`/forwarding boundaries in `src/README.md`; new compiler modules must be
  tracked by the build and `driver.py`'s `COMPILER_SOURCES` cache identity.
  Update runtime declarations, effects and ABI checks together. Explain intentional
  IR-contract changes; never mechanically refresh snapshots to silence failures.

Lessons from reviewed changes (links are evidence, not claims about today's open work):

| Failure pattern | Rule to carry forward |
|---|---|
| Another `iter()` masked a missing iterator helper ([#633](https://github.com/den-run-ai/pystachy/pull/633)) | Keep dependency regressions in separate programs; test all annotation spellings. |
| Inferring `Any` erased concrete generator channels ([#633](https://github.com/den-run-ai/pystachy/pull/633)) | Preserve yield/send/return contracts independently. `Any` specializes concrete types; it does not add dynamically typed storage. |
| An unresolved empty-container allocation could serve pointer-bearing callers ([#603](https://github.com/den-run-ai/pystachy/pull/603)) | Mark storage pointer-free only after representation is proven; test copy, growth, clear/refill and shared template results under GC. |
| A lazily created global needed an explicit collector root ([#602](https://github.com/den-run-ai/pystachy/pull/602)) | Test survival after caller references disappear, including aliases and extension initialization. |
| A C `float` declared as `double` compiled but returned zeros ([#609](https://github.com/den-run-ai/pystachy/pull/609)) | Verify ABI widths, mutation, aliasing and pointer lifetime with real C calls; twin parity alone cannot establish ABI correctness. |
| Import counts barely changed after real feature fixes ([#635](https://github.com/den-run-ai/pystachy/pull/635)) | Record the next blocker and functional API delta; one removed blocker does not establish whole-package support. |
| Cancelled runs retained queued final jobs ([#643](https://github.com/den-run-ai/pystachy/pull/643)) | Inspect run/job state and concurrency; a skipped summary is not successful verification. |

## State compatibility and performance precisely

- Separate **import compilation**, **working APIs**, **adapted ports**, **upstream
  tests** and **embedded CPython**. Throwing stubs are diagnostic probes, not
  implementations. Native ndarray/BLAS examples do not prove native NumPy support.
  A prototype should name a real consumer it unblocks, or say that none is verified.
- Use `tools/import_sweep.py` and existing port/audit tooling before inventing a
  census. Pin compiler/source/input versions and overlay exclusions; changing the
  denominator is not necessarily lost coverage. Retain exact repros and first
  errors. Preserve dated reports; add a measured checkpoint to the rolling log.
- Keep upstream provenance, licenses, hashes and `# Pystachy port:` explanations.
  A small adaptation should remain runnable under CPython when that is its contract.
  Try unchanged upstream first, then minimal adaptations; avoid library-name special
  cases where a general compiler fix is appropriate.
- Check outputs/checksums before measuring. Distinguish original CPython, adapted
  CPython, old Pystachy and new Pystachy baselines; JIT startup/compilation, AOT build
  and steady-state execution are separate costs. Record flags, hardware, input size,
  samples and shared-host load. Compare both JIT and AOT; a win in one can hurt the other.
  Include short, sparse, adversarial and repeated-use inputs around the optimized case.
  Prefer deterministic operation/allocation bounds for CI. Report noisy timing
  differences as inconclusive, and retain memory/GC trade-offs alongside speedups.

## Coordinate, publish and hand off

- Keep changes scoped; separate risky runtime/inference experiments from routine
  fixes. Search related issues/PRs before extending scope. Resolve overlapping
  edits with their owner; do not reset, clean, force-push or remove another session's
  work. If direct session messaging is unavailable, use authorized PR/issue updates
  for coordination and say what remains unconfirmed.
- When integrating stacks, preserve both sides' runtime hooks, shared tables,
  test registrations and workflow checks. Follow dependency order, refresh each
  dependent base after its predecessor lands and review the combined diff.
  A clean textual merge is not semantic validation.
- Recheck the live PR head, base, review threads and **all applicable workflows**
  immediately before merging, when merging is authorized. CI on an old head or an
  older merge base is historical evidence. Validate the combined tree with current
  main, use an expected-head SHA where supported, and recheck main after merging.
  Green CI alone does not make an experimental PR ready; unresolved scope/design
  risks remain reasons to keep it draft.
- Distinguish queued/running, failed, cancelled/skipped and `action_required` runs.
  No jobs created can mean fork workflow approval is pending. Inspect the cause;
  do not bypass approvals or cancel other sessions' useful runs. A failed/quota-limited
  Codex review is neither a code finding nor completed review. Read actual findings,
  reproduce them and arrange review through available authorized means.
- PR descriptions should state the problem, resulting behavior, scope/remaining
  limits, linked issues and exact validation revision/commands/results. Separate
  local evidence from CI; update stale status after revisions. Keep old measurements
  labeled with their revision. Use a structured body or `--body-file` for multiline
  text. Verify that the published tree contains the files you reviewed.
- Close an issue only when its acceptance scope is met on merged main. Use `Refs`
  for partial work, narrow the residual scope and link existing follow-ups before
  creating duplicates. A merged PR or better diagnostic alone may not close a tracker.
- Before stopping or handing off, leave a concrete summary: branch/worktree and
  commit/PR, changed behavior, tests completed/failed/not run, live jobs you own,
  remaining risks and the next action. Preserve authorized work in commits/pushed
  branches or a draft PR as appropriate; do not leave the next session reconstructing
  unreported edits. Stop or transfer owned background work when asked to stop.

Keep this file compact: add durable lessons, link detailed evidence, remove obsolete
rules, and keep transient task status in the relevant PR/issue or handoff.
