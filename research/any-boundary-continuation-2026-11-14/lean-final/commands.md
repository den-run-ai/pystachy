# Commands and execution context

These are recorded commands from the completed and interrupted attempts. The orchestration used Python stdin; no standalone Lean orchestration script was created. The final source and checker identities are in `run/initial-manifest.json`; the recovery policy and preserved failures are in `run/resume2-recovery-manifest.json`.

Working directory: `/workspace/scratch/1a96cd11db0d/lean-report-qa`. The checked source was `2df26bde21451abb89cc487f57b0a5531c655b8d`.

## Recorded report invocations

### Initial attempt

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python tools/lean_report.py --jobs 2 --start-method spawn --progress --records /workspace/scratch/1a96cd11db0d/lean-qualification/final-2df26bde/whole.jsonl
```

### First official resume

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python tools/lean_report.py --jobs 2 --start-method spawn --resume --progress --records /workspace/scratch/1a96cd11db0d/lean-qualification/final-2df26bde/whole.jsonl
```

### Completed official resume

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python tools/lean_report.py --jobs 1 --start-method spawn --resume --progress --records /workspace/scratch/1a96cd11db0d/lean-qualification/final-2df26bde/whole.resume2.jsonl
```

## Completed stage commands

### whole-report-resume2

Exit status: 0. Elapsed wall time: 1881.546 seconds.

```sh
make lean-report PY=/workspace/scratch/c2b093657c17/dev-venv/bin/python 'LEAN_REPORT_FLAGS=--jobs 1 --start-method spawn --resume --progress --records /workspace/scratch/1a96cd11db0d/lean-qualification/final-2df26bde/whole.resume2.jsonl'
```

### report-status

Exit status: 0. Elapsed wall time: 14.879 seconds.

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python tools/lean_report.py --status
```

### strict-storage

Exit status: 0. Elapsed wall time: 322.611 seconds.

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python tools/check_lean_storage_corpus.py --jobs 1 --progress --report /workspace/scratch/1a96cd11db0d/lean-qualification/final-2df26bde/storage.json
```

## Original environment

The completed official resume and strict-storage gate overrode `PYSTACHY_JOBS` to `1`; the initial attempt used `2`. Other recorded variables follow.

```json
{
  "PATH": "/workspace/scratch/c2b093657c17/dev-venv/bin:/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18/bin:/workspace/scratch/c2b093657c17/toolchains/lean-4.35.0-linux/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
  "PYSTACHY_LLVM": "/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18/bin",
  "PYSTACHY_JOBS": "2",
  "LEAN_BOUNDARY_REQUIRED": "1",
  "LD_LIBRARY_PATH": "/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18/lib"
}
```

## Reproduction notes

Use a clean checkout of public source `adf5a12a147649d01018dd49c8167610812ada00`, Python 3.13.16, LLVM 18.1.3 and Lean 4.35.0 as recorded in the identity manifest. Set local tool paths and choose new output paths. For a fresh full run, omit `--resume`; use the official `--resume` only with a provenance-matching complete historical header and its corresponding records. Do not insert selected-program replays into a whole-corpus ledger. The original runs used the tools' default timeouts; none was relaxed.

The three independent patched-generator replay command vectors and outputs are preserved in `review/optional-delegate-overflow-patched-review.json`, with matching probe sources and logs. The original failing/control evidence is preserved alongside them.
