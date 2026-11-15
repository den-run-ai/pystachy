# Verification preflight for 527dc89a

Read-only inspection on 2026-11-15. No build, test, timing, or corpus-parity run was started for this preflight. The worktree was clean at `527dc89a02e8e8866fc4d83997847663a6e7c0aa`.

## Full verification

`Makefile:331` invokes `PY="$(PY)" tests/verify.sh`. The default/full `all` plan contains **58 stages**. `VERIFY_PROFILE=pr` selects a different, sampled alternate-configuration plan and must not be called full verification.

The full plan covers fresh compiler/runtime bootstrap, hosted IR parity, native JIT/AOT, optimizer-off execution, runtime caches, Python-free rebuild/execution, UBSan, compiler/program GC checks, benchmarks/examples, opt-in dynamic Any/promoting integers, annotation widening, IR/runtime/library/resource contracts, FFI/embedding/extensions, and scaling. The explicit plan can be recorded without starting work:

```sh
cd /workspace/scratch/9f30aa4fd4fd/pystachy
VERIFY_PROFILE=full tests/verify.sh --list
```

### Available prerequisites

| Item | Verified state |
| --- | --- |
| Required CPython | `.python-version` is 3.13.16. `/workspace/scratch/c2b093657c17/dev-venv/bin/python` is 3.13.16. The default system `python3.13` is 3.13.5. |
| Shared CPython | The pinned Python has `Py_ENABLE_SHARED=1` and an existing `libpython3.13.so.1.0` under `/workspace/scratch/c2b093657c17/toolchains/python/cpython-3.13.16-linux-x86_64-gnu/lib`. |
| LLVM | `/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18/bin` contains matching LLVM 18.1.3 tools. `clang` and `opt` version commands also work with an empty environment and only `/usr/bin:/bin` on PATH. Default PATH has no usable LLVM tools. |
| UBSan | The same LLVM payload contains the x86-64 standalone/minimal UBSan runtimes and compiler-rt archives. `tools/setup.sh --check` does not check UBSan/BLAS availability. |
| System tools | `/usr/bin/cc`, `/usr/bin/ld`, and `/usr/bin/localedef` exist. |
| Development tools | The pinned venv matches Ruff 0.17.3, mypy 2.4.1, shellcheck-py 0.11.0.1 and typing_extensions 4.16.0 from `tools/requirements-dev.txt`. |
| Space at inspection | `/workspace`: 18 GiB free of 63 GiB. `/tmp`: 1.3 GiB free of a 4.9 GiB tmpfs. Current build directory: 124 MiB. Use a workspace TMPDIR. |

### Suggested full command

Run this as a foreground command through the yielding execution tool. Do not append `&`: inherited ignored SIGINT breaks the signal-handling checks. Keep sources frozen and run no other heavy build or timing job concurrently.

```sh
cd /workspace/scratch/9f30aa4fd4fd/pystachy
export PATH=/workspace/scratch/c2b093657c17/dev-venv/bin:$PATH
export PYSTACHY_LLVM=/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18/bin
export PYSTACHY_JOBS=2
export TMPDIR=/workspace/scratch/9f30aa4fd4fd/evidence/verify-tmp
unset VERIFY_BOOTSTRAP_DIR
mkdir -p "$TMPDIR"
VERIFY_PROFILE=full make PY=/workspace/scratch/c2b093657c17/dev-venv/bin/python verify > /workspace/scratch/9f30aa4fd4fd/evidence/make-verify.log 2>&1
verify_status=$?
printf '%s\n' "$verify_status" > /workspace/scratch/9f30aa4fd4fd/evidence/make-verify.status
if [ -f build/verification.json ]; then
  cp build/verification.json /workspace/scratch/9f30aa4fd4fd/evidence/verification.json
fi
exit "$verify_status"
```

### Pitfalls and completion criteria

- Every invocation deletes `build/verify` and `build/verification.json`. Archive any previous reports first. Separate groups in the same checkout are not concurrent-safe.
- Local full verification builds its own fresh bootstrap. The existing native compiler/fixed points do not skip that work. CI bootstrap reuse has source/toolchain/run checks and is unavailable for local `all`/`bootstrap`.
- `PYSTACHY_JOBS=2` bounds case workers, but some independent runtime/contract lanes still run concurrently inside the script. There is no documented global single-worker switch for those lanes.
- The Python-free lane runs `env -i`, retaining only its tool whitelist, TMPDIR, home, LLVM path and worker limit. A toolchain depending on inherited LD_LIBRARY_PATH would fail there; the inspected LLVM executables pass empty-environment version checks.
- The FFI script skips all `py_`/extension cases, while allowing a successful exit, if its selected Python is older than 3.12 or lacks shared libpython. Retain `build/verify/ffi.log` and verify its summary does not report those skips. The script supplies its own matching `PYTHONHOME`/`PYSTACHY_LIBPYTHON` for embedded runs. A missing optional German locale is separately recorded by matching twins.
- `gc-self` has its existing ten-minute bound. Preserve any timeout evidence; do not widen it to make the report pass.
- A full pass needs report `profile="full"`, `group="all"`, `result="pass"`, `summary.steps=58`, `summary.passed=58`, `summary.failed=0`, all 58 expected step names, correct corpus counts, the frozen commit, and `git.dirty=false`. Inspect per-step failure/skip details rather than relying only on the final exit code.
- This target does not replace separate lint, Lean, recording, optional BLAS, or packaging gates. BLAS provider comparisons are relevant to ndarray/BLAS changes, not an implicit stage-separation prerequisite.
- No duration or peak-disk estimate was established by this read-only preflight. Monitor free workspace space and the running log.

## Retained 4,579-input parity

Original evidence is under `/workspace/scratch/78a63a74ecb5/pipeline-irsame-details/`:

- `irsame-retain.sh`: the maintained comparator with only result-retention/cwd changes.
- `harness-changes.json`: exact modifications and SHA-256 identities.
- `ordinary-replay-command.json`: the historical command and environment.
- `ordinary-summary.json`: 4,579 completed cases, 2,653 accepted by both, 1,926 rejected by both, zero raw-diagnostic/IR/status differences or new rejections.
- `ordered-corpus.json`, `ordinary-case-results.json`: complete ordered identities/results.
- `shared-home.Eu23yT/`: completed per-case reports/status/messages. The separate `shared-home.kbbGyj/` is an interrupted IRCHECK run and must not be treated as complete evidence.

Do **not** execute the old retained script directly for the new run: its cwd and active-output pointer are hardcoded to the previous session. Make an evidence-local copy with those two path prefixes changed.

The maintained `tools/irsame.sh` is byte-identical in both trees (SHA-256 `7baa4d09a86103485f6b6c87a739162347b97542051d80b6cfb57c8a108587d5`). The historical retained harness SHA-256 is `77d8885734710d1cf937e300381a28d439585b9e993918e7bd6c695f37c6b52e`.

### Current identity checks (read-only)

- Current ordered corpus still has exactly 4,579 paths, matching `ordered-corpus.json` in order. Their input file contents match the old source tree.
- All 105 actual files under `lib`, `ryu`, `mpz`, plus `runtime.c` and `runtime.py`, match both the #1499 home and the original main-reference home. The comparison includes actual files, excluding CPython `__pycache__`/`.pyc` files; it is not a tracked-files-only comparison.
- Common `PYSTACHY_HOME` is therefore justified for this compiler-only comparison. Otherwise embedded library path strings can cause IR differences even with identical file contents. Preserve the common-home method and input identity in the report.
- Native #1499 reference: `/workspace/scratch/78a63a74ecb5/pystachy/pystachy`, 6,724,320 bytes, SHA-256 `33c0fb45f19776c5f1f9c96252f4c82af89e267ffbfc82f376eff165823dd757`.
- Native candidate: `/workspace/scratch/9f30aa4fd4fd/pystachy/pystachy`, 6,729,184 bytes, SHA-256 `25af1f17f712d599cf73164f1ec6481afa47e5a534a986347d56bb850fc46f28`.
- Original main 8049014 reference, if a second comparison is desired: `/workspace/scratch/78a63a74ecb5/pystachy/build/ref/pystachy`, SHA-256 `ab6eab3cd16a215ae483a4bd8ca6a5219cecbcff62f89e58e6b01d9f08a9233a`. Distinguish this comparison from the direct #1499 follow-up.

### Prepare the retained harness (does not run compilers)

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python - <<'PY'
import hashlib
import json
from pathlib import Path

original = Path('/workspace/scratch/78a63a74ecb5/pipeline-irsame-details/irsame-retain.sh')
output = Path('/workspace/scratch/9f30aa4fd4fd/evidence/irsame')
output.mkdir(exist_ok=True)
source = original.read_text()
assert hashlib.sha256(original.read_bytes()).hexdigest() == '77d8885734710d1cf937e300381a28d439585b9e993918e7bd6c695f37c6b52e'
changes = {
    '/workspace/scratch/78a63a74ecb5/pystachy': '/workspace/scratch/9f30aa4fd4fd/pystachy',
    '/workspace/scratch/78a63a74ecb5/pipeline-irsame-details': str(output),
}
for old, new in changes.items():
    assert old in source
    source = source.replace(old, new)
harness = output / 'irsame-retain.sh'
harness.write_text(source)
harness.chmod(0o755)
(output / 'harness-copy.json').write_text(json.dumps({
    'source': str(original),
    'source_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
    'destination_sha256': hashlib.sha256(harness.read_bytes()).hexdigest(),
    'path_substitutions': changes,
}, indent=2) + '\n')
PY
```

### Run the direct #1499 comparison

Run separately from full verification and timing work. The clean environment below leaves IRCHECK unset and uses default optimizations, as the historical complete 4,579-case run did. No Python interpreter/LLVM tools are needed by these native IR-only compiler commands.

```sh
cd /workspace/scratch/9f30aa4fd4fd/pystachy
env -i PATH=/usr/bin:/bin \
  TMPDIR=/workspace/scratch/9f30aa4fd4fd/evidence/irsame \
  PYSTACHY_HOME=/workspace/scratch/9f30aa4fd4fd/pystachy \
  PYSTACHY_JOBS=2 \
  /workspace/scratch/9f30aa4fd4fd/evidence/irsame/irsame-retain.sh \
  /workspace/scratch/78a63a74ecb5/pystachy/pystachy \
  /workspace/scratch/9f30aa4fd4fd/pystachy/pystachy \
  > /workspace/scratch/9f30aa4fd4fd/evidence/irsame/run.log 2>&1
parity_status=$?
printf '%s\n' "$parity_status" > /workspace/scratch/9f30aa4fd4fd/evidence/irsame/run.status
exit "$parity_status"
```

The copied harness retains `corpus` and 1-based numbered case directories. Every case must contain `status` (two exit codes), `report`, `old.msg`, and `new.msg`. It retains LLVM files on mismatches; matching LLVM files are deleted after the maintained comparator checks them. Diagnostic normalization remains the maintained behavior, so separately compare raw messages to support the stronger raw-diagnostic identity claim.

### Summarize the retained run

This post-run read records per-case results, detects missing/abnormal exits, and fails unless exactly 4,579 cases completed without raw-message or comparator differences. Also record command/environment, source commit/clean status, input manifests, and compiler hashes before/after the actual run; the preflight identities above cannot replace end-of-run checks.

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python - <<'PY'
from collections import Counter
import hashlib
import json
from pathlib import Path

out = Path('/workspace/scratch/9f30aa4fd4fd/evidence/irsame')
cases = Path((out / 'active-shared-home-dir').read_text().strip())
paths = (cases / 'corpus').read_text().splitlines()
rows, problems = [], []
counts = Counter()
raw_diffs = report_diffs = new_rejections = completed = 0
for index, path in enumerate(paths, 1):
    case = cases / str(index)
    required = ('status', 'report', 'old.msg', 'new.msg')
    missing = [name for name in required if not (case / name).is_file()]
    if missing:
        problems.append({'index': index, 'path': path, 'missing': missing})
        continue
    status = (case / 'status').read_text().split()
    if len(status) != 2 or any(x not in ('0', '1') for x in status):
        problems.append({'index': index, 'path': path, 'abnormal_status': status})
        continue
    a, b = map(int, status)
    old, new = (case / 'old.msg').read_bytes(), (case / 'new.msg').read_bytes()
    same_raw = old == new
    empty = (case / 'report').stat().st_size == 0
    completed += 1
    counts[f'{a}->{b}'] += 1
    raw_diffs += not same_raw
    report_diffs += not empty
    new_rejections += a == 0 and b != 0
    rows.append({'index': index, 'path': path, 'old_exit': a, 'new_exit': b,
                 'raw_diagnostics_identical': same_raw, 'report_empty': empty,
                 'old_diagnostic_sha256': hashlib.sha256(old).hexdigest(),
                 'new_diagnostic_sha256': hashlib.sha256(new).hexdigest()})
passed = (len(paths) == completed == 4579 and not problems and
          not raw_diffs and not report_diffs and not new_rejections and
          not any(a != b for a, b in (key.split('->') for key in counts)))
summary = {'status': 'passed' if passed else 'failed', 'programs': len(paths),
           'completed_reports': completed, 'exit_counts': dict(counts),
           'raw_diagnostic_differences': raw_diffs,
           'ir_or_report_differences': report_diffs, 'new_rejections': new_rejections,
           'case_directory': str(cases), 'problems': problems}
(out / 'case-results.json').write_text(json.dumps(rows, indent=2) + '\n')
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
raise SystemExit(0 if passed else 1)
PY
```

