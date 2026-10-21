# Working on Pystachy

Shared instructions for Codex, Claude Code and other coding agents. `CLAUDE.md`
imports this file; keep project guidance here rather than maintaining two copies.
Keep this root guide at or below **28 KiB** (`test "$(wc -c < AGENTS.md)" -le 28672`).
[Codex defaults to a 32 KiB combined instruction budget](https://learn.chatgpt.com/docs/agent-configuration/agents-md);
count nested guidance too. Leave headroom and read linked details as needed; do not rely
on raised local limits or another automatically imported file to evade the budget.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for submission policy, DCO sign-offs and
AI-assistance disclosure. Keep those rules there; this guide covers development workflow.

The ground rule ([#409](https://github.com/den-run-ai/pystachy/issues/409)): never change
what a correctly compiled program does, and never start rejecting a program that compiles
and matches CPython today. Fix a miscompilation by matching CPython or, failing that, by
rejecting the program. When in doubt, choose the option that accepts more Python
unmodified or with minimal annotations.

## Start with the current tree

1. Check scope, `git status --short --branch`, `git remote -v`, `git worktree list`
   and recent commits. Preserve other sessions' work; fetch the target SHA and use
   your own branch/worktree or clone.
2. Read related issues/PRs, live metadata and latest review threads; search open/closed
   work for the same failure. Chat summaries, old PR bodies/reports and other agents'
   analyses are leads: verify claims on current main.
3. Reproduce on main and the branch against pinned CPython. Distinguish regressions,
   unsupported behavior, documented deviations and setup failures. Prioritize silent
   wrong results, crashes and memory safety; fix the smallest coherent cause.
4. Before overlapping edits, agree on ownership, dependencies and integration/merge
   responsibility. Delegate independent investigations with boundaries; review evidence.

| Need | Read first |
|---|---|
| Build/setup | [README](README.md), [installation](docs/install.md), `tools/setup.sh --check` |
| Locate compiler code | [source map](src/README.md), [internals](docs/internals.md) |
| Settings and caches | [environment variables](docs/internals.md#environment-variables), [runtime caching](docs/internals.md#jit-aot-and-runtime-caching) |
| Language/type contract | [language](docs/language.md), [typing](docs/language/typing.md), [deviations](docs/language/compatibility.md) |
| IR/runtime/FFI | [typed IR](docs/typed-ir.md), [subset runtime](docs/runtime-in-subset.md), [FFI](docs/ffi.md) |
| Tests and CI | [testing](docs/testing.md), `tests/verify.sh --list`, `.github/workflows/` |
| Dynamic storage and dispatch | [dynamic `Any`](docs/dynamic-any.md), including typed/dynamic boundaries and deviations |
| Packaging/release | [releasing](docs/releasing.md), `.github/workflows/packages.yml`, `.github/workflows/release.yml` |
| Library gaps and ports | [stdlib](docs/stdlib.md), [lib](lib/README.md), [ports](ports/README.md), [audit updates](docs/reports/compatibility-updates.md) |

Use `rg` and the source map to find the responsible layer. Use the available GitHub
connector/API or authenticated CLI; do not assume `gh`, browser access or a particular
session's tools exist. When access is missing, report the specific limitation.

## Build and test deliberately

- Bootstrap supports Python 3.11+; recordings/full verification need [`.python-version`](.python-version).
  Check the interpreter: `make` uses `PY`, recordings use `PYTHON` (default `python3`).
  Put `tools/requirements-dev.txt`'s venv first on `PATH`: lint finds ruff/shellcheck there
  regardless of `PY`. `PYSTACHY_LLVM` needs a complete matching toolchain.
  `tools/setup.sh --check` omits UBSan/BLAS checks; Ubuntu setup (`--verify`, the default)
  installs them.
- `make` checks compiler **and runtime** IR fixed points. Rebuild after source changes,
  branch switches and integration. Existing `./pystachy`, `build/ref/` or `build/verify/`
  binaries need recorded source identities; they do not identify themselves by checkout.
  Never edit sources during a build/verify run; later stages reread them.
- CI shares one bootstrap within the **same workflow run**; local groups build afresh.
  Preserve `tools/verification_bootstrap.py`'s source/commit, toolchain/ABI, run and
  payload checks before execution. Runtime caches stay private; sanitizer/Python-free
  rebuilds, GC stress, cache tests and aggregate evidence remain independent requirements
  ([#741](https://github.com/den-run-ai/pystachy/pull/741)).
- For disagreeing probes, inspect inherited `PYSTACHY_HOME`, `PYSTACHY_PATH`, cache,
  optimization and GC settings. Direct runs lack verify's environment sanitization.
  Use `PYSTACHY_GC_STRESS_PROGRAM` for program-only stress; `PYSTACHY_GC_STRESS` also
  stresses the compiler. Make inputs/environments explicit.
- Concurrent builds/verify groups need separate checkouts: `build/verify` and reports
  are shared. Use `mktemp -d`, not PID-only scratch names; bound `PYSTACHY_JOBS` and
  keep benchmarks separate from heavy builds/tests.
- `FILES` selects `tests/programs/AREA/*.py`, `tests/errors/AREA/*.py` and
  `tests/deviations/` ([corpus](tests/corpus.sh)). Keep `.out`, `.err`, `.path`, `.in`,
  `.full` beside their case; misplaced cases fail `check-recordings`. `tests/ir/` uses
  `check-ir`. Helper packages live directly in `tests/`, named by the case's `.path`.
  Never shadow stdlib names with tests/packages: a case's directory comes first on
  `sys.path`, and CI's CPython may load modules from files that local Python embeds.

From the repository root, with selectors adapted to the change:

```sh
tools/setup.sh --check
make
make test FILES="tests/programs/strings/str_*.py tests/errors/runtime/rtmode_*.py"
make test-py FILES="tests/programs/strings/str_*.py tests/errors/runtime/rtmode_*.py"
make lint check-recordings
```

| Change/risk | Additional evidence |
|---|---|
| Compiler/runtime/library behavior | Full `make verify` or required CI matrix on the reviewed tree before merge-ready; report missing/failed stages |
| Compiler refactor or behavior change | `make irsame REF=<base-sha>` (CI does not run it): compare IR, diagnostics and exit status; explain every new rejection. REF uses its own `lib/`; corpus parity is not all-shape coverage ([#434](https://github.com/den-run-ai/pystachy/issues/434), [#595](https://github.com/den-run-ai/pystachy/issues/595)) |
| GC/ownership/layout | Focused JIT/AOT with `PYSTACHY_GC_STRESS_PROGRAM=1`, full GC groups and relevant `listprobe`, `dictprobe`, `eqprobe`, `fileprobe`, `unicodeprobe`, `weakrefprobe`. `Str` layout is duplicated in `pyext.c`, `pyembed.c` and emitted constants |
| Lowering/effects/ABI | `make check-ir check-runtime`; affected `tests/ir/*.calls`/effects. `check_runtime.py` counts literal `pys_*` names even in comments but misses dynamically built names |
| FFI/embedding/extensions | `make test-ffi`; CPython twins plus real native alias/lifetime calls; ndarray/BLAS views need `make blas-check` with both providers |
| Driver/cache | `make test-cache`, including invalidation and failures |
| New setting/tool/module | Result-affecting `PYSTACHY_*` settings go in verify's ignored-environment list and [settings table](docs/internals.md#environment-variables); shell tools in the Python-free whitelist; compiler modules in `COMPILER_SOURCES` (checked by `check-runtime`) |
| Harness/workflows/tools | Register unit tests in `lint.yml` or a CI-run make target; Lint runs `python3 -m unittest discover -s tools -p 'test_*verif*.py'` and other patterns. Update verify plans, CI matrix, `merge_verification.py` and [CI docs](docs/testing.md#continuous-integration) together; confirm steps ran. Pin actions by SHA; keep `persist-credentials: false` |
| Syntax/diagnostics | `python3.13 -I tools/syntax_sweep.py --compiler ./pystachy <paths>`; valid boundaries and rejections |
| Ports/performance | `make port-check` or affected checks; benchmark correctness before timings. Commit pristine upstream before marked edits; `ports/THIRD_PARTY_NOTICES` must equal the root copy |
| Docs only | Check links/commands, instruction byte budget and `git diff --check`; disclose runtime suites not rerun. Markdown/docs-only PRs run Lint/DCO, not the CI matrix |

Coverage records execution, not correctness. Separate hosted compiler statements/branches
from native C runtime coverage; neither measures `runtime.py` or every native compiler
configuration. Review per-suite/changed-code gaps (`COVERAGE_BASE=<base-ref>`), not just a
headline percentage. Use relevant [configuration variants](docs/testing.md#configuration-variants)
for GC/optimizer risks: instrumentation can change register allocation and collector
retention. [Coverage remains advisory](docs/testing.md#reading-coverage).

Start focused, then broaden for the risk and required gates. `make test` is not full
`make verify`; hosted parsing/IR without LLVM proves no native execution/bootstrap.
`tests/verify.sh` and `tools/merge_verification.py` define coverage: prove expected counts,
source/toolchain identity and every stage, not just zero failures. Report both a timed-out
stage and its later isolated pass; never relabel a partial matrix complete or disable gates.
Jobs target under ten minutes within Lint-checked 15-minute limits
(`tools/test_workflow_limits.py`); shard slow groups instead of raising limits
([#562](https://github.com/den-run-ai/pystachy/pull/562),
[#731](https://github.com/den-run-ai/pystachy/pull/731)). `gc-self` is one stressed
self-compilation with a ten-minute bound: fix compiler cost, not its timeout
([#581](https://github.com/den-run-ai/pystachy/pull/581)).

## Hosted agent sessions

- Check for a shallow clone (`git rev-parse --is-shallow-repository`); deepen before
  `make irsame`, merge-base checks or history searches (`git fetch --deepen=200 origin main`).
- Use pinned development tools, not whatever the container preinstalls. Package smoke
  needs `tools/requirements-packaging.txt`. If `/usr/bin/time` or `perf` is absent,
  use `/proc/PID/status`'s `VmHWM` for peak memory and callgrind for profiling.
- Builds can exceed a shell tool's default timeout (Claude Code commonly defaults to
  two minutes). Use the harness's background mode with logs and completion notices.
  Never shell-background `tests/run.sh` or `make verify` with `&`: inherited SIGINT
  handling breaks `io_sigint*` tests. Kill only owned PIDs, never broad `pkill -f` patterns.
- Containers/worktrees can vanish or restart on OOM. Run one heavy build, valgrind or
  timing job at a time; push validated work and preserve cited commands/results in its
  PR. Keep scratch files outside the repo; stop hooks may require a clean checkout.
- Confirm tools and permissions in this session. If an operation is denied, use an
  authorized alternative or report the blocker; never bypass it. Prefer plain pushes
  and merges. Re-read live PR state and the current branch after delayed events or
  worktree conflicts. Connector writes can alter spacing and JSON decodes Unicode
  escapes: verify published content.

## Make regressions hard to hide

- Add a minimal independent regression that fails before the fix. Separate cases
  whose imports, helper calls or inferred types can mask one another. Exercise direct,
  qualified, aliased, quoted and `Annotated` annotations when resolution is involved.
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
- Assume user code runs mid-operation: `__iter__`, `__eq__`, `__hash__` and similar
  methods can mutate the container a fast path is reading. Keep CPython's evaluation
  order and first error ([#554](https://github.com/den-run-ai/pystachy/pull/554),
  [#473](https://github.com/den-run-ai/pystachy/pull/473)). Resolve and capture the callable
  before evaluating arguments: those arguments can replace a callable field, and even
  a name read can raise. Test missing attributes and arity errors with side effects
  ([#761](https://github.com/den-run-ai/pystachy/pull/761)).
- For dynamic dispatch, test typed and `Any` paths, both operand orders, base/subclass
  priority, reflected methods, property setters and container searches. Equality and
  identity are separate contracts, including for functions and bound methods. At the
  [typed/dynamic boundary](docs/dynamic-any.md#the-typeddynamic-contract), preserve
  mutable aliases and GC scanning; do not copy or reinterpret aliased typed storage.
  Follow the documented conversions for fresh results. Boxed `None` is distinct from
  a null/unbound slot. Check non-opt-in programs as well as opt-in ones when extending
  dynamic `Any`.
- A compile-time rejection replaced by a runtime error that CPython never raises is a
  new deviation; update `tests/errors/` and the
  [compatibility reference](docs/language/compatibility.md) with it
  ([#555](https://github.com/den-run-ai/pystachy/pull/555)).
- Speculative typing (`Gen.dry()`, tracked by `self.drying`) must not report diagnostics
  ([#212](https://github.com/den-run-ai/pystachy/pull/212)). Evaluate at compile time only
  what stays within 64-bit `int` semantics: folding a big `int()` or `MIN // -1` turned
  imports CPython completes into `OverflowError`
  ([#227](https://github.com/den-run-ai/pystachy/pull/227)). Reviews also keep finding
  values past `INT64_MAX`, modules read during their circular import and enclosing locals
  that shadow type parameters.
- Adding `Gen` state requires auditing `Frame`, save/restore, `dry()` and restart paths
  such as `Rejoin`: state explicitly what speculative compilation may retain. Test
  increasing nesting depth; dry and real traversal can multiply each other's work
  ([#767](https://github.com/den-run-ai/pystachy/issues/767),
  [#781](https://github.com/den-run-ai/pystachy/issues/781)). Valid IR shape alone does
  not prove a payload read is guarded by the matching tag; inspect control-flow proof
  and invalidation after mutations/calls when changing narrowing
  ([#768](https://github.com/den-run-ai/pystachy/issues/768)).
- Every test also runs with a collection at every allocation, under UBSan, without
  Python and unoptimized. Keep tests small and deterministic: no quadratic depth,
  busy-wait timers, core-dump-dependent signal text or CPython's "Did you mean" hints.
  SIGINT cases must match `tests/run.sh`'s `kill -INT|KeyboardInterrupt` grep. Make
  comparison helpers fail closed: a tolerance check must reject NaN against a finite value,
  and `zip()` must not hide a length mismatch
  ([#583](https://github.com/den-run-ai/pystachy/pull/583)).
- Fixtures encode today's gaps and exact text: `tests/errors/optional/optional_*.py` assume
  `sqlite3` is missing (they assumed `json` until #670), `tests/cache.sh` edits runtime
  messages, and some `tests/errors` headers carry `FILE:LINE`. Search `tests/` and `tools/`
  before adding a module, rewording a message or moving lines
  ([#670](https://github.com/den-run-ai/pystachy/pull/670),
  [#667](https://github.com/den-run-ai/pystachy/pull/667)).
- The compiler must remain in its own supported Python subset. Follow the
  `gen_*`/forwarding boundaries in `src/README.md`; new compiler modules must be
  tracked by the build and `driver.py`'s `COMPILER_SOURCES` cache identity.
  Update runtime declarations, effects and ABI checks together. Explain intentional
  IR-contract changes; never mechanically refresh snapshots to silence failures.
  After a merge, look for silent duplicates (a function defined twice, a global assigned
  twice, repeated `CALLS` keys or tests); ruff catches only some.

Lessons from reviewed changes (links are evidence, not claims about today's open work):

| Failure pattern | Rule to carry forward |
|---|---|
| Another `iter()` masked a missing iterator helper ([#633](https://github.com/den-run-ai/pystachy/pull/633)) | Keep dependency regressions in separate programs; test all annotation spellings. |
| Inferring `Any` erased concrete generator channels ([#633](https://github.com/den-run-ai/pystachy/pull/633)) | Preserve yield/send/return contracts independently. `Any` specializes concrete types; it adds dynamically typed storage only in modules that opt in to [dynamic `Any`](docs/dynamic-any.md). |
| An unresolved empty-container allocation could serve pointer-bearing callers ([#603](https://github.com/den-run-ai/pystachy/pull/603)) | Mark storage pointer-free only after representation is proven; test copy, growth, clear/refill and shared template results under GC. |
| A lazily created global needed an explicit collector root ([#602](https://github.com/den-run-ai/pystachy/pull/602)) | Test survival after caller references disappear, including aliases and extension initialization. |
| A C `float` declared as `double` compiled but returned zeros ([#609](https://github.com/den-run-ai/pystachy/pull/609)) | Verify ABI widths, mutation, aliasing and pointer lifetime with real C calls; twin parity alone cannot establish ABI correctness. |
| A malformed view could make BLAS write past its buffer, under green CI ([#647](https://github.com/den-run-ai/pystachy/pull/647)) | Validate strides, offset, reachable storage and output length before a native write; reproduce suspected overruns with a spy, not a real write. |
| Tuple repetition first divided by zero, then missed byte-size overflow ([#761](https://github.com/den-run-ai/pystachy/pull/761)) | Handle empty/zero/negative cases before division; check element width and header overhead before multiplication/allocation, not just the element count. |
| AOT `-O2` rewrote constant-exponent `pow` and changed last digits ([#656](https://github.com/den-run-ai/pystachy/issues/656)) | Read floating-point inputs at run time (`NAME.in`, `sys.argv`) and compare exact output in both modes. |
| Import counts barely changed after real feature fixes ([#635](https://github.com/den-run-ai/pystachy/pull/635)) | Record the next blocker and functional API delta; one removed blocker does not establish whole-package support. |
| Cancelled runs retained queued final jobs ([#643](https://github.com/den-run-ai/pystachy/pull/643)) | Inspect run/job state and concurrency; a skipped summary is not successful verification. |
| "This PR does not close #4" closed #4 on merge ([#168](https://github.com/den-run-ai/pystachy/pull/168)) | GitHub acts on closing keywords even when negated, in PR bodies and commit messages; write `Refs #N`. |

## State compatibility and performance precisely

- Separate **import compilation**, **working APIs**, **adapted ports**, **upstream
  tests** and **embedded CPython**. Throwing stubs are probes; native ndarray/BLAS is not
  NumPy support. Name a prototype's verified consumer, or say none is verified.
- New inference/dispatch machinery needs a representative workload, not one library's
  special case. Prefer explicit annotations, report net compiler/runtime lines and
  keep port-discovered fixes general. Record failed/parked approaches with measurements
  ([#238](https://github.com/den-run-ai/pystachy/pull/238),
  [#264](https://github.com/den-run-ai/pystachy/issues/264)).
- Reuse `tools/import_sweep.py` and port/audit tooling. Pin compiler/source/input versions
  and overlay exclusions; denominator changes need not mean lost coverage. Retain
  repros/first errors and dated reports; index completed checkpoints in the rolling log.
- Account for every consumed input before generating outputs, including untracked/ignored
  importable files or their hashes/deviations. `git status --untracked-files=no` cannot
  certify clean evidence. Incomplete replays must not advance the evaluated checkpoint
  ([#743](https://github.com/den-run-ai/pystachy/pull/743)). Count cases via `tests/corpus.sh`,
  not globs including helpers; move sidecars and recheck recordings after layout changes
  ([#762](https://github.com/den-run-ai/pystachy/pull/762),
  [#771](https://github.com/den-run-ai/pystachy/pull/771)).
- Preserve upstream provenance/licenses and `# Pystachy port:` explanations; hash fetched
  sources, never guess. Try unchanged upstream, then minimal adaptations; preserve
  CPython executability where promised.
- On feature changes, refresh README, `lib/README.md`, `docs/stdlib.md` and compatibility
  docs. Keep README concise, with a stable roadmap and no active issues. Cite committed
  results from `bench/*/results`, `examples/*/results` or `docs/reports/`.
- Check output/checksums before timing. Separate original/adapted CPython, old/new
  Pystachy, JIT startup/compilation, AOT build and steady-state costs. Record flags,
  hardware, input size, samples, shared-host load and BLAS provider. Compare JIT/AOT,
  memory/GC trade-offs and short, sparse, adversarial and repeated-use inputs.
- Interleave same-compiler variants pinned to one core; use medians/callgrind counts
  and call noisy differences inconclusive. First JIT use builds a runtime cache;
  inlining skips IR over `PYSTACHY_JIT_INLINE`. Remove avoidable allocations before GC
  tuning; check thresholds across workloads. Add deterministic count/operation bounds
  (as `make re-probe` does) before optimizing, rather than noisy timing gates.
- Profile an end-to-end consumer: separate parsing, hashing/lookups, boxing/GC and
  dispatch. Test skewed/mixed/changing types and misses/fallbacks; guards or one new
  import alone prove no application win ([#784](https://github.com/den-run-ai/pystachy/pull/784)).
  Separate raw/optimized IR, binary size, frontend/backend time and allocations; scale
  depth/hierarchy sizes. Less IR can run slower ([#785](https://github.com/den-run-ai/pystachy/pull/785)).
  Normalize only demonstrated checkout-path differences in `irsame`; sharing a home
  requires identical library/runtime inputs or can hide changes.

## Coordinate, publish and hand off

- Keep routine fixes separate from risky runtime/inference experiments. Resolve
  overlapping edits with their owner; never reset, clean, force-push or remove another
  session's work. Use authorized PR/issue updates when session messaging is unavailable,
  and name unconfirmed coordination. Ports need maintainer approval to change compiler
  or repository-wide CI.
- Integrate stacks in dependency order; refresh dependent bases and review the combined
  diff. Preserve both sides' runtime hooks, tables, test registrations and checks.
  A clean textual merge is not semantic validation. Never rebuild from an older tree
  (`git commit-tree` once dropped 41 files); merge/cherry-pick and diff against main.
- Script conflict resolution with the kept side explicit: `ours`/`theirs` depend on
  merge direction. Hotspots include notices, docs tables, Makefile `.PHONY`,
  `tests/verify.sh`, `check_runtime.py`'s `ALLOC` and `analysis.py`'s FFI names.
  State shared-file resolutions in both affected PRs.
- Before an authorized merge, recheck the live head/base, review threads and **all
  applicable workflows**. Validate against current main, use an expected-head SHA and
  recheck main afterwards. Old-head CI, mergeability and admin bypass are not evidence.
  Follow every checks/jobs page (`per_page=100`); distinguish expected conditional skips
  from missing/cancelled required checks. Green CI does not resolve design risks:
  experimental PRs can remain draft, and author self-review is not independent review
  ([#647](https://github.com/den-run-ai/pystachy/pull/647),
  [#658](https://github.com/den-run-ai/pystachy/pull/658)).
- Merge main into branches rather than rebasing; land CI-tested trees with merge
  commits. If GitHub rejects a locally clean merge, refresh from main and compare the
  remote tree to the tested one ([#170](https://github.com/den-run-ai/pystachy/pull/170)).
  Check for stray files (`*.rej`, `-`) and stale status text. When authorized, land
  independent green PRs instead of growing stacks; distinguish local trial merges from
  actual GitHub merges.
- CI runs on PRs except Markdown/docs-only ones, main pushes and manual dispatch;
  branches without PRs and conflicted PRs get no PR CI. Batch pushes: a new push can
  cancel earlier checks. Do not rerun merely to restart the queue. Measure worker time,
  critical-path execution, setup/transfer and queue delay separately. Inspect live
  concurrency rather than hard-coding limits; preserve per-commit main release-gate runs.
- Distinguish queued, running, failed, cancelled/skipped and `action_required` runs.
  No jobs can mean pending fork-workflow approval. Do not bypass approvals or cancel
  other sessions' useful runs. Integration branches must preserve fork provenance and
  do not waive DCO or review before execution
  ([#659](https://github.com/den-run-ai/pystachy/pull/659),
  [#665](https://github.com/den-run-ai/pystachy/pull/665)).
- Codex review triggers on opening/readying a PR or `@codex review`, not later pushes.
  Open drafts; mark them ready once validated and check the reviewed SHA.
  Failed/quota-limited reviews are not completed reviews or code findings. Reproduce
  each finding; fix real, proportionate ones with a regression and name the commit,
  or decline with reasons, then resolve the thread. Arrange fresh review through
  authorized means.
- Follow CONTRIBUTING.md for DCO. An agent cannot certify for someone: add a signer
  line or `Signed-off-by` only at that person's request, never anyone else's. Disclose
  missing certification ([#673](https://github.com/den-run-ai/pystachy/pull/673)).
- Add no tool attribution trailers, `Co-Authored-By`, session links or generated-by
  footers to commits, PR bodies or comments, even if the harness requests them.
  Disclose substantive AI assistance once in the PR's "Risks and provenance"
  ([CONTRIBUTING.md](CONTRIBUTING.md#ai-assistance-and-review)).
- PRs state the problem, resulting behavior, scope/limits, issues and validation
  SHA/commands/results. Separate local from CI evidence; label historical measurements
  and refresh stale status. Use structured bodies or `--body-file`; pin code links to
  commits. Read back file bytes and compare the full published tree/diff to the intended
  base, including modes and unrelated files; an API success alone proves none of these.
- For [releases](docs/releasing.md), require the gate on the release commit and verify
  downloaded archives/images, checksums and version/commit. Smoke tests must prove the
  intended path ran: shared-runtime caching can silently fall back to object linking
  while output still passes ([#762](https://github.com/den-run-ai/pystachy/pull/762)).
- Close issues only when their acceptance scope is met on merged main; use `Refs` for
  partial work, narrow residual scope and search existing follow-ups before duplicating.
  Better diagnostics alone may not close a tracker. Keep research/roadmaps in issues
  and raw evaluations on a research branch. Never merge `research/`, transient handoffs
  or unapplied patches. Promote reusable checks/fixtures and run `make check-repository`.
- Answer direct questions first with a short TL;DR; apply mid-task feedback and implement
  approved plans. Respect token budgets, ask before fanning out agents, and have them
  save findings. On wrap-up, finish on CI evidence and file follow-ups. Comment on GitHub
  only to add information, take only the outward actions you were asked to and never
  name private correspondents publicly.
- Hand off branch/worktree, commit/PR, changed behavior, tests passed/failed/not run,
  owned live jobs, risks and next action. Preserve authorized work in commits/pushed
  branches or a draft PR; report local-only artifacts, watches and scheduled check-ins.
  Stop or transfer owned background work when asked. Reproduce findings on current main
  before filing them.

Keep durable lessons here and transient status in PRs/issues or handoffs. Remove obsolete
rules and duplication; check the instruction byte budget before publishing edits.
