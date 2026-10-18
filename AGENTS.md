# Working on Pystachy

Shared instructions for Codex, Claude Code and other coding agents. `CLAUDE.md`
imports this file; keep project guidance here rather than maintaining two copies.
This is an onboarding guide, not a snapshot of open issues or CI status.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for submission policy, DCO sign-offs and
AI-assistance disclosure. Keep those rules there; this guide covers development workflow.

The ground rule ([#409](https://github.com/den-run-ai/pystachy/issues/409)): never change
what a correctly compiled program does, and never start rejecting a program that compiles
and matches CPython today. Fix a miscompilation by matching CPython or, failing that, by
rejecting the program. When in doubt, choose the option that accepts more Python
unmodified or with minimal annotations.

## Start with the current tree

1. Read the user's scope, `git status --short --branch`, `git remote -v`,
   `git worktree list` and recent commits. Preserve other sessions' uncommitted work.
   Fetch the target branch, record its SHA and use your own branch/worktree or clone.
2. Read the relevant issue, linked PRs, latest review threads and live PR metadata.
   Search open and closed issues and PRs for the same minimal failure before starting
   another implementation or issue. Old chat summaries, PR bodies, dated reports and
   analyses pasted from other agents are leads, not current-state evidence; re-check
   each claim on current main.
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
| Settings and caches | [environment variables](docs/internals.md#environment-variables), [runtime caching](docs/internals.md#jit-aot-and-runtime-caching) |
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
  `tools/setup.sh --check` does not look for the UBSan runtime and BLAS libraries that
  `make verify` needs; on Ubuntu, plain `tools/setup.sh` (`--verify`) installs them.
  `make lint` runs the `ruff` and `shellcheck` found on `PATH`, whatever `PY` is, so put
  the development venv's `bin` first.
- `make` checks compiler **and runtime** IR fixed points. Rebuild after compiler or
  runtime changes, branch switches and integration. An existing `./pystachy`,
  `build/ref/` or `build/verify/` executable is not proof of which sources it contains.
  If reusing a verified binary, record its source identity separately from the checkout.
  Do not edit the tree while `make` or a verify group runs: later stages read it again.
- When ad hoc probes disagree, inspect inherited `PYSTACHY_HOME`, `PYSTACHY_PATH`,
  cache, optimization and GC settings; full verification sanitizes coverage-changing
  options, but direct invocations may not. Keep probe inputs and environments explicit.
  `PYSTACHY_GC_STRESS` stresses the compiler too, which is slow; use
  `PYSTACHY_GC_STRESS_PROGRAM` to stress only the program.
- Keep concurrent builds/verification groups in separate checkouts: `build/verify`
  and the report path are shared. Use `mktemp -d` for scratch probes; PID-only names
  can collide across sessions. Bound `PYSTACHY_JOBS` on shared hosts. Do not run
  timing benchmarks alongside heavy builds or broad test jobs.
- `FILES` takes top-level `tests/*.py` programs and `tests/errors/` and
  `tests/deviations/` cases. `tests/ir/` probes run through `make check-ir`, and other
  subdirectories hold helper modules; the git pathspec `'tests/*.py'` matches those too,
  `':(glob)tests/*.py'` does not. Do not name test files or packages after stdlib modules:
  `tests/record.sh` runs cases with `tests/` first on `sys.path`, and CI's python.org
  CPython loads more modules (such as `binascii`) from files that a test can shadow.

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
| Code-generation-preserving refactor | `make irsame REF=<base-sha>`; compare diagnostics/exit status as well as IR. The reference compiler uses REF's own `lib/`, so `lib/` changes show as IR differences |
| Other compiler changes | `make irsame REF=<main-sha>` too, which CI does not run: explain every newly rejected program and changed exit status ([#434](https://github.com/den-run-ai/pystachy/issues/434), [#595](https://github.com/den-run-ai/pystachy/issues/595)). The corpus does not cover every shape |
| GC, ownership, container layout | Focused JIT/AOT with `PYSTACHY_GC_STRESS_PROGRAM=1`; relevant `listprobe`, `dictprobe`, `eqprobe`, `fileprobe`, `unicodeprobe`, `weakrefprobe`; full GC groups. `Str`'s layout is repeated in `pyext.c`, `pyembed.c` and emitted constants |
| Lowering, effects, runtime ABI | `make check-ir check-runtime`; affected `tests/ir/*.calls`/effect contracts. `check_runtime.py` treats every literal `pys_*` name in compiler source, comments included, as a runtime reference, and sees no name built with an f-string |
| FFI, embedding, extensions | `make test-ffi`; CPython twins and actual native calls, with alias/lifetime cases; `make blas-check` with both BLAS providers for ndarray/BLAS views |
| Driver/runtime cache | `make test-cache`; invalidation and failure paths |
| New setting, shell tool or module | Add a `PYSTACHY_*` setting that can change results to `tests/verify.sh`'s ignored-environment list and the [settings table](docs/internals.md#environment-variables); a shell utility the driver or tests call to the python-free stage's tool list; a compiler module to `COMPILER_SOURCES` (`make check-runtime` checks it) |
| Verification harness, workflows, `tools/` | Lint, not CI, runs `python3 -m unittest discover -s tools -p 'test_*verif*.py'` and the other `lint.yml` patterns; register a new test file there or in a make target that CI runs. Change a group's plan, the CI matrix, `merge_verification.py` and [CI docs](docs/testing.md#continuous-integration) together, then confirm the new steps ran. Pin actions by commit SHA; keep `persist-credentials: false` |
| Syntax/diagnostics | `python3.13 -I tools/syntax_sweep.py --compiler ./pystachy <paths>`; valid boundaries and rejection fixtures |
| Ports/performance | `make port-check` or affected port checks; relevant benchmark correctness target before timings. Commit the unmodified upstream file before the marked edits; `ports/THIRD_PARTY_NOTICES` must equal the root file |
| Docs only | Check links, commands and `git diff --check`; disclose that runtime suites were not rerun. CI still runs the full matrix |

Start with the focused reproducer, then broaden for the affected risk and required gates.
`make test` covers JIT/AOT but is not the full `make verify` matrix. A hosted parse or
IR check without LLVM is not a native execution or bootstrap result. The authoritative
plan and coverage checks live in `tests/verify.sh` and `tools/merge_verification.py`;
do not duplicate a fixed job count here. Verification must prove expected counts,
source/toolchain identity and every required stage, not just a zero-failure excerpt.
If a stage times out and passes alone, report both outcomes; do not relabel the original
partial matrix as a complete pass. Do not disable gates to make a run green. A CI group
over its job limit is cancelled even when its tests passed; groups target under ten
minutes, so shard a slow one instead of raising the limit
([#562](https://github.com/den-run-ai/pystachy/pull/562)). `gc-self` is a single
GC-stressed self-compilation with its own ten-minute bound: a change that slows every
compilation must be fixed in the compiler
([#581](https://github.com/den-run-ai/pystachy/pull/581)).

## Hosted agent sessions

Cloud agents (Claude Code on the web, Codex cloud and similar) run in disposable
containers but share the repository, issues and CI with other sessions. These points
were checked in a 4-vCPU Claude Code container on 2026-10-18 (`44316e7`); confirm yours.

- The clone may be shallow (`git rev-parse --is-shallow-repository`). Deepen it, for
  example with `git fetch --deepen=200 origin main`, before `make irsame`, merge-base
  checks or history searches.
- `tools/setup.sh` installed the missing UBSan runtime and OpenBLAS in seconds. The
  preinstalled `ruff` was not the pinned version and `shellcheck` was missing: use a venv
  from `tools/requirements-dev.txt`. `tools/package_smoke.py` needs the uv and setuptools
  pins in `packages.yml`. `/usr/bin/time` and `perf` were absent: read `VmHWM` in
  `/proc/PID/status` for peak memory and profile with callgrind.
- `make` took 3 minutes and `make test` 8 (4,456 checks); `make check-recordings` and
  Lint's `tools/` tests took about a minute each. Each verify group bootstraps first, so
  use CI for the full matrix.
- Tool calls time out (Claude Code's Bash: 2 minutes by default, 10 at most) and `sleep`
  may be blocked. Run long commands in the harness's background mode with a log file and
  act on the completion notice. Do not start `tests/run.sh` or `make verify` with a shell
  `&`: asynchronous jobs ignore SIGINT, so the `io_sigint*` cases fail or hang.
- Never use `pkill -f` or a broad `pgrep` pattern; it has killed agents' own shells and
  other runs. Kill the PIDs you started.
- Containers, scratch space and worktrees vanish with the session, and a container that
  runs out of memory restarts mid-session, killing background jobs and agents. Run one
  heavy build, valgrind or timing job at a time, push validated work early, and put the
  commands, logs and measurements you cite in the PR or issue. A stop hook may require a
  clean checkout, so keep scratch files outside the repository.
- Here `gh` had an invalid token and GraphQL was blocked (`gh pr list` failed); REST reads
  through `gh api repos/...` worked, writes went through the GitHub connector, and branch
  deletion was refused (HTTP 403), so leave cleanup lists to the owner. Connector tools
  have dropped footers and rewritten non-ASCII spacing, and tool-call JSON decodes
  `\uXXXX` escapes: re-read what you write.
- Permission classifiers may refuse force-pushes, branch replacement, compound
  `git stash` commands or a merge only its author reviewed; use plain pushes and merges,
  get explicit authorization or ask, never a workaround. Event wake-ups can be late or
  missing, and `git checkout` refuses a branch checked out in another worktree: re-read
  live PR state and `git branch --show-current` before acting.

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
  [#473](https://github.com/den-run-ai/pystachy/pull/473)).
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
- Every test also runs with a collection at every allocation, under UBSan, without
  Python and unoptimized. Keep tests small and deterministic: no quadratic depth,
  busy-wait timers, core-dump-dependent signal text or CPython's "Did you mean" hints.
  SIGINT cases must match `tests/run.sh`'s `kill -INT|KeyboardInterrupt` grep. Make
  comparison helpers fail closed: a tolerance check must reject NaN against a finite value,
  and `zip()` must not hide a length mismatch
  ([#583](https://github.com/den-run-ai/pystachy/pull/583)).
- Fixtures encode today's gaps and exact text: `tests/errors/optional_*.py` assume `json`
  is missing, `tests/cache.sh` edits runtime messages, and some `tests/errors` headers
  carry `FILE:LINE`. Search `tests/` and `tools/` before adding a module, rewording a
  message or moving lines ([#670](https://github.com/den-run-ai/pystachy/pull/670),
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
| Inferring `Any` erased concrete generator channels ([#633](https://github.com/den-run-ai/pystachy/pull/633)) | Preserve yield/send/return contracts independently. `Any` specializes concrete types; it does not add dynamically typed storage. |
| An unresolved empty-container allocation could serve pointer-bearing callers ([#603](https://github.com/den-run-ai/pystachy/pull/603)) | Mark storage pointer-free only after representation is proven; test copy, growth, clear/refill and shared template results under GC. |
| A lazily created global needed an explicit collector root ([#602](https://github.com/den-run-ai/pystachy/pull/602)) | Test survival after caller references disappear, including aliases and extension initialization. |
| A C `float` declared as `double` compiled but returned zeros ([#609](https://github.com/den-run-ai/pystachy/pull/609)) | Verify ABI widths, mutation, aliasing and pointer lifetime with real C calls; twin parity alone cannot establish ABI correctness. |
| A malformed view could make BLAS write past its buffer, under green CI ([#647](https://github.com/den-run-ai/pystachy/pull/647)) | Validate strides, offset, reachable storage and output length before a native write; reproduce suspected overruns with a spy, not a real write. |
| AOT `-O2` rewrote constant-exponent `pow` and changed last digits ([#656](https://github.com/den-run-ai/pystachy/issues/656)) | Read floating-point inputs at run time (`NAME.in`, `sys.argv`) and compare exact output in both modes. |
| Import counts barely changed after real feature fixes ([#635](https://github.com/den-run-ai/pystachy/pull/635)) | Record the next blocker and functional API delta; one removed blocker does not establish whole-package support. |
| Cancelled runs retained queued final jobs ([#643](https://github.com/den-run-ai/pystachy/pull/643)) | Inspect run/job state and concurrency; a skipped summary is not successful verification. |
| "This PR does not close #4" closed #4 on merge ([#168](https://github.com/den-run-ai/pystachy/pull/168)) | GitHub acts on closing keywords even when negated, in PR bodies and commit messages; write `Refs #N`. |

## State compatibility and performance precisely

- Separate **import compilation**, **working APIs**, **adapted ports**, **upstream
  tests** and **embedded CPython**. Throwing stubs are diagnostic probes, not
  implementations. Native ndarray/BLAS examples do not prove native NumPy support.
  A prototype should name a real consumer it unblocks, or say that none is verified.
- Do not let one target library drive open-ended inference or dispatch growth: new
  type-system machinery needs its own workload. Prefer explicit annotations, report net
  compiler/runtime lines, keep bugs found through a port as general fixes, and record
  parked or failed approaches with their measurements in an issue
  ([#238](https://github.com/den-run-ai/pystachy/pull/238),
  [#264](https://github.com/den-run-ai/pystachy/issues/264)).
- Use `tools/import_sweep.py` and existing port/audit tooling before inventing a
  census. Pin compiler/source/input versions and overlay exclusions; changing the
  denominator is not necessarily lost coverage. Retain exact repros and first
  errors. Preserve dated reports; add a measured checkpoint to the rolling log.
- Keep upstream provenance, licenses, hashes and `# Pystachy port:` explanations.
  A small adaptation should remain runnable under CPython when that is its contract.
  Try unchanged upstream first, then minimal adaptations; avoid library-name special
  cases where a general compiler fix is appropriate. Compute provenance hashes from the
  fetched upstream file, never from memory.
- When a feature lands, search the README, `lib/README.md`, `docs/stdlib.md` and the
  compatibility docs for statements it makes stale. Add only the reports a PR's claims
  need. Keep the README concise, with a stable roadmap and no active issues, and take its
  numbers from committed results (`bench/*/results`, `examples/*/results`, `docs/reports/`).
- Check outputs/checksums before measuring. Distinguish original CPython, adapted
  CPython, old Pystachy and new Pystachy baselines; JIT startup/compilation, AOT build
  and steady-state execution are separate costs. Record flags, hardware, input size,
  samples and shared-host load. Compare both JIT and AOT; a win in one can hurt the other.
  Include short, sparse, adversarial and repeated-use inputs around the optimized case.
  Prefer deterministic operation/allocation bounds for CI. Report noisy timing
  differences as inconclusive, and retain memory/GC trade-offs alongside speedups.
- Compare variants built by the same compiler, pinned to one core and interleaved, using
  medians or callgrind instruction counts; sequential runs on a shared host have shown
  changes that interleaving removed. The first JIT run also builds the runtime cache, and
  JIT inlining skips programs over `PYSTACHY_JIT_INLINE` lines of IR. Name the BLAS
  provider in comparisons. Check GC threshold changes on several workloads, and remove
  avoidable allocations before tuning the collector. Land a benchmark driver with
  deterministic count guards (as `make re-probe` does) before optimizing.

## Coordinate, publish and hand off

- Keep changes scoped; separate risky runtime/inference experiments from routine
  fixes. Search related issues/PRs before extending scope. Resolve overlapping
  edits with their owner; do not reset, clean, force-push or remove another session's
  work. If direct session messaging is unavailable, use authorized PR/issue updates
  for coordination and say what remains unconfirmed. A port should not change the
  compiler or repository-wide CI without the maintainer's go-ahead.
- When integrating stacks, preserve both sides' runtime hooks, shared tables,
  test registrations and workflow checks. Follow dependency order, refresh each
  dependent base after its predecessor lands and review the combined diff.
  A clean textual merge is not semantic validation. Never rebuild a branch from an older
  tree (`git commit-tree` once dropped 41 files); replay with merges or cherry-picks and
  diff the result against main.
- Name the kept side explicitly when scripting conflict resolution; `ours` and `theirs`
  swap with merge direction. Conflict hotspots: `THIRD_PARTY_NOTICES`, README and docs
  tables, the Makefile's `.PHONY` line, `tests/verify.sh`, `check_runtime.py`'s `ALLOC`
  and `analysis.py`'s FFI names. When two open PRs edit one, state the resolution in both.
- Recheck the live PR head, base, review threads and **all applicable workflows**
  immediately before merging, when merging is authorized. CI on an old head or an
  older merge base is historical evidence. Validate the combined tree with current
  main, use an expected-head SHA where supported, and recheck main after merging.
  Green CI alone does not make an experimental PR ready; unresolved scope/design
  risks remain reasons to keep it draft. Green PRs have waited for an independent
  adversarial review of the exact head
  ([#647](https://github.com/den-run-ai/pystachy/pull/647),
  [#658](https://github.com/den-run-ai/pystachy/pull/658)), and the authoring session's
  own review is not independent. A mergeable state is not CI evidence: branch protection
  did not require the verification gate (on 2026-10-18 only a DCO check), and admins
  bypass it. Page check runs with `per_page=100`; the default page of 30 is shorter than
  one push's list.
- `main` contains only merge commits: bring main into a branch by merging, not rebasing,
  and land stacks so each merge publishes a CI-tested tree. GitHub can refuse, or call
  dirty, a merge that is clean locally (criss-cross merge bases); merge main into the
  branch, push and compare the remote tree with the tested one
  ([#170](https://github.com/den-run-ai/pystachy/pull/170)). Before merging, check the
  diff for stray files (`*.rej`, a file named `-`) and stale status text. When merging is
  authorized, prefer landing green, independent PRs to growing stacks, and say whether a
  merge you report was a local trial or happened on GitHub.
- CI runs on pull requests, pushes to main and manual dispatch, so a branch without a PR
  gets none, and no `pull_request` workflow runs while a PR has conflicts. Each push
  queues about 30 jobs (about ten minutes) and cancels the PR's previous run: batch
  commits, and do not push or rerun only to restart checks.
- Distinguish queued/running, failed, cancelled/skipped and `action_required` runs.
  No jobs created can mean fork workflow approval is pending. Inspect the cause;
  do not bypass approvals or cancel other sessions' useful runs. To validate or extend
  a fork PR, cherry-pick it onto current main in your own branch and PR
  ([#659](https://github.com/den-run-ai/pystachy/pull/659),
  [#665](https://github.com/den-run-ai/pystachy/pull/665)).
- Codex reviews a PR when it is opened, marked ready for review or given an
  `@codex review` comment, not after later pushes: open drafts, mark them ready once
  validated, and check which commit a review covers. A failed/quota-limited Codex review
  is neither a code finding nor completed review. Read actual findings, reproduce them
  and arrange review through available authorized means. Answer every bot thread: fix
  real, proportionate findings with a regression and name the commit, or decline with
  reasons; then resolve it.
- An agent cannot certify the DCO: never add someone's `Signed-off-by`. CONTRIBUTING.md
  says which PRs need a sign-off; where one does, leave it to the human contributor and
  say so in the PR checklist ([#673](https://github.com/den-run-ai/pystachy/pull/673)).
- PR descriptions should state the problem, resulting behavior, scope/remaining
  limits, linked issues and exact validation revision/commands/results. Separate
  local evidence from CI; update stale status after revisions. Keep old measurements
  labeled with their revision. Use a structured body or `--body-file` for multiline
  text. Verify that the published tree contains the files you reviewed. Link code at
  a commit SHA, not a branch.
- Close an issue only when its acceptance scope is met on merged main. Use `Refs`
  for partial work, narrow the residual scope and link existing follow-ups before
  creating duplicates. A merged PR or better diagnostic alone may not close a tracker.
  Put research findings and roadmaps in issues, and raw evaluation records on a
  separate research branch rather than in the docs of open PRs.
- Answer the maintainer's direct questions first, after a short TL;DR; replies are often
  read on a phone. Apply feedback that arrives mid-task before continuing, and once a plan
  is approved, implement it rather than drifting into triage. Keep effort proportional:
  treat a stated token budget as a cap, ask before fanning out agents (and have them save
  findings as they go), and when asked to wrap up, finish on CI evidence and file
  follow-ups. Comment on GitHub only to add information, take only the outward actions you
  were asked to, and never name private correspondents publicly.
- Before stopping or handing off, leave a concrete summary: branch/worktree and
  commit/PR, changed behavior, tests completed/failed/not run, live jobs you own,
  remaining risks and the next action. Preserve authorized work in commits/pushed
  branches or a draft PR as appropriate; do not leave the next session reconstructing
  unreported edits. Stop or transfer owned background work when asked to stop. Re-run
  findings on current main before filing them, and list local-only artifacts, PR
  watches and scheduled check-ins you leave behind.

Keep this file compact: add durable lessons, link detailed evidence, remove obsolete
rules, and keep transient task status in the relevant PR/issue or handoff.
