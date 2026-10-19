# Built-in prototype integration

The merge-preparation revision is a stack rooted at main
`a355c83ff7b60b64e3264867593064c3da9611a5`:

| PR | Change | Base |
|---|---|---|
| [#644](https://github.com/den-run-ai/pystachy/pull/644) | `_imp` | pinned main |
| [#645](https://github.com/den-run-ai/pystachy/pull/645) | `_ast` | #644 branch |
| [#646](https://github.com/den-run-ai/pystachy/pull/646) | `select` | #645 branch |
| [#648](https://github.com/den-run-ai/pystachy/pull/648) | `_weakref` | #646 branch |

The #648 branch contains all four prototypes, including reconciled module
registrations, both C probe targets, and both required verification steps. The
Makefile also preserves current main's Unicode probe and BLAS targets. Its
collector retains `weakrefs_sweep`, `files_sweep` and CPython embedding's
`trk_sweep` after marking and before reclaiming storage. None retains a target.
The weak-reference probe tests a shared weak/CPython-tracked owner and verifies
that collection clears the weak target and queues its release token exactly once.

## Reproduce

Fetch the combined branch, or replace the branch name with the exact head SHA
recorded in #648's validation checkpoint. Record `git rev-parse HEAD` with results:

```sh
git fetch origin codex/prototype-weakref-20261017
git switch --detach FETCH_HEAD
git rev-parse HEAD
tools/setup.sh --check
make
make lint check-recordings check-runtime
make selectprobe weakrefprobe
```

Both C probe make targets run normally and with collection at every allocation.
Run every added/modified public test (including explicit rejection tests) with
the bootstrapped compiler, normally and with program GC stress:

```sh
cases=$(git diff --name-only --diff-filter=AM \
  a355c83ff7b60b64e3264867593064c3da9611a5 HEAD -- tests | \
  sed -nE '/^tests\/(errors\/|deviations\/)?[^/]+\.py$/p')
tests/run.sh ./pystachy 'jit aot' $cases
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' $cases
PYSTACHY_OPT=-all PYSTACHY_GC_STRESS_PROGRAM=1 \
  tests/run.sh ./pystachy 'jit aot' tests/lib_weakref_transition.py
make test-ffi
make verify
```

The full `make verify` is a separate gate. Focused checks, C probes, or a partial
local run do not imply that it passed. Each PR's original head had 31/31 green
CI checks; revision-head CI results are separate and linked from the PRs.

## Remaining boundaries

These prototypes establish selected APIs and native runtime behavior. They do
not establish working upstream unittest, pytest, pyperf or CPython regrtest.

- `_imp.is_builtin` raises; fixing the earlier `_io` import error alone cannot
  enable importlib.
- `_ast.__match_args__` is available, but compiler `match` statements and
  NamedTuple inheritance still reject explicitly. `_field_types` is absent.
- Native `select` uses `pselect` to avoid losing SIGINT at the wait boundary.
  `select.error`, other polling backends, selectors and subprocess remain outside
  the supported scope.
- No standard-library weakref consumer is unblocked yet. `import weakref` fails,
  `_weakrefset.WeakSet()` fails compilation, and callbacks, weak mappings and
  finalization remain unsupported. (Reference equality and hashing were added after
  this integration; see the [weakref contract](weakref.md).)

See the individual prototype documents for exact contracts and pinned CPython,
PyPy and GraalPy references. Import-only progress is not evidence that a consumer's
APIs work.
