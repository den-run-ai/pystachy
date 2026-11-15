# Completed compiler-stage corpus parity

The retained comparison **passed all 4,579 inputs** on 2026-11-15. It compared the original PR #1499 native compiler with the follow-up native compiler, using the same absolute input paths and a common, byte-identical library/runtime home.

| Result | Count |
| --- | ---: |
| Completed inputs | 4,579 |
| Accepted by both compilers | 2,653 |
| Rejected by both compilers | 1,926 |
| LLVM/comparator differences | 0 |
| Raw diagnostic differences | 0 |
| Exit-status differences | 0 |
| New rejections | 0 |
| Missing or abnormal results | 0 |

The comparator exited 0 and printed `4579 programs identical`. The full local execution-verification run continued separately during this comparison. This was an IR/diagnostic parity run, without native rebuilds, LLVM machine-code generation, application execution, or performance measurement. It establishes parity for this corpus and configuration, not equivalence for every program.

## Source, input and binary identities

| Role | Recorded identity |
| --- | --- |
| Candidate commit | `eabfe7b3d8f1be3e4615442423c7d3fbab10285b` |
| Original PR checkout commit | `800752d8a582bff77d4c375039af786b82a96f73` |
| Candidate native binary SHA-256 | `25af1f17f712d599cf73164f1ec6481afa47e5a534a986347d56bb850fc46f28` |
| Original PR native binary SHA-256 | `33c0fb45f19776c5f1f9c96252f4c82af89e267ffbfc82f376eff165823dd757` |
| Maintained comparator SHA-256 | `7baa4d09a86103485f6b6c87a739162347b97542051d80b6cfb57c8a108587d5` |
| Retained comparator SHA-256 | `2c803cd54f1576b0ebb331c1349e3662e08d2164ab9b8daddc86ab3e8a57bf97` |

The candidate and reference checkouts were clean. The before/after records are byte-identical and cover both executables, all 4,579 ordered corpus inputs, 61 compiler source files, 9,045 fixture/dependency files, and 105 actual library/runtime input files in each home. The library/runtime records include `lib`, `ryu`, `mpz`, `runtime.c` and `runtime.py`; CPython bytecode and `__pycache__` files are excluded. Actual files and symlinks are recorded rather than only Git-tracked filenames. Equal library/runtime inputs justify using the common home; the command does not hide differing library contents behind path normalization.

The [preflight record](preflight-identity.json.gz) additionally establishes that the ordered corpus paths/contents match the earlier qualification and that the original main-reference home has the same library/runtime inputs. It is separate from the executed run's [before](before.json.gz) and [after](after.json.gz) records.

## Archived evidence

| Artifact | Contents |
| --- | --- |
| [summary.json](summary.json) | Complete counts, commits, compiler hashes, configuration and identity result. |
| [case-results.json.gz](case-results.json.gz) | All 4,579 ordered results, exit codes and both raw diagnostic hashes. |
| [before.json.gz](before.json.gz), [after.json.gz](after.json.gz) | Full source, fixture, input, harness and executable identities around execution. |
| [preflight-identity.json.gz](preflight-identity.json.gz) | Earlier preparation-only identity checks. |
| [raw-cases.tar.gz](raw-cases.tar.gz) | Ordered corpus plus every case's raw status, comparator report and two diagnostics. |
| [command.json](command.json) | Exact original command, working directory and complete child environment. |
| [run.log](run.log), [run.status](run.status) | Comparator completion message and exit status. |
| [irsame-retain.sh](irsame-retain.sh), [harness-copy.json](harness-copy.json) | Comparator and its recorded retention/path provenance. |
| [run_parity.py](run_parity.py), [summarize.py](summarize.py) | Original execution wrapper, identity recorder and summarizer. |

The deterministic gzip files restore the original JSON bytes exactly. Their compressed/uncompressed byte lengths and SHA-256 digests are in the [compression manifest](../../compressed-artifacts.json).

The raw archive contains exactly **18,317 unique regular files**: `corpus`, then `status`, `report`, `old.msg` and `new.msg` for each 1-based case directory from `1` through `4579`. There are no symlink or directory entries. Its SHA-256 is `3e0d48225fb929587f1a425f5d7691ed264a346202d0960e8e3c403f137394b3`.

Every comparator report is empty. The 9,158 diagnostic files match pairwise and match the hashes in the case-results record; each compiler's diagnostics total 326,901 bytes. Matching LLVM files were deleted only after the maintained comparator checked their bytes. They are not in this archive, so independently repeating the LLVM comparisons requires replaying the compilers. The archive preserves the comparison results, diagnostics and provenance.

An independent archive audit checked every member against the summary and case results, restored all four compressed IR JSON records, confirmed byte-identical before/after records, and rehashed the recorded inputs and executables against the frozen workspace. It also reconstructed the retained comparator from the unchanged maintained comparator plus the previously recorded retention changes and the two path-prefix substitutions. No compiler was run for that audit.

## Audit the archived results without running compilers

From this directory, restore only the records needed by the summarizer into a new temporary directory:

```sh
archive_dir=$(pwd)
parity_audit=$(mktemp -d)
for name in before after; do
  gzip -dc "$archive_dir/$name.json.gz" > "$parity_audit/$name.json"
done
cp "$archive_dir/summarize.py" "$archive_dir/run.status" "$parity_audit/"
mkdir "$parity_audit/raw"
tar -xzf "$archive_dir/raw-cases.tar.gz" -C "$parity_audit/raw"
printf '%s\n' "$parity_audit/raw" > "$parity_audit/active-shared-home-dir"
python3.13 "$parity_audit/summarize.py"
```

This writes a fresh summary and case-results file under `parity_audit`. The case-directory path will identify the extracted archive rather than the original workspace; counts, hashes and recorded source/binary identities should agree. This checks the archive's internal consistency without requiring the original compiler paths. It does not independently regenerate the deleted LLVM files or authenticate the recorded inputs.

## Replay the comparison

The original invocation was:

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python /workspace/scratch/9f30aa4fd4fd/evidence/irsame/run_parity.py
```

The retained scripts intentionally preserve the historical absolute paths. In the recorded workspace, the existing reference binary is `/workspace/scratch/78a63a74ecb5/pystachy/pystachy`; the candidate binary and common home are under `/workspace/scratch/9f30aa4fd4fd/pystachy`. The wrapper uses two workers, default optimizations and IRCHECK unset, with only `PATH`, `TMPDIR`, `PYSTACHY_HOME` and `PYSTACHY_JOBS` in the child environment. It refuses an unclean candidate checkout, a corpus other than 4,579 paths, unequal library/runtime inputs, or existing execution evidence. It never builds either compiler.

For another run in that workspace, first confirm the recorded checkouts and binary identities. Then copy only the three runner files into a fresh evidence directory and adapt the retained harness's output prefix. From this archive directory:

```sh
parity_replay=$(python3.13 - "$PWD" <<'PY'
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

archive = Path(sys.argv[1]).resolve()
fresh = Path(tempfile.mkdtemp(prefix="parity-replay-",
    dir="/workspace/scratch/9f30aa4fd4fd/evidence"))
for name in ("run_parity.py", "summarize.py", "irsame-retain.sh"):
    shutil.copy2(archive / name, fresh / name)
harness = fresh / "irsame-retain.sh"
original = harness.read_bytes()
old_prefix = "/workspace/scratch/9f30aa4fd4fd/evidence/irsame"
assert old_prefix in original.decode()
harness.write_text(original.decode().replace(old_prefix, str(fresh)))
(fresh / "replay-path-change.json").write_text(json.dumps({
    "original_harness_sha256": hashlib.sha256(original).hexdigest(),
    "replay_harness_sha256": hashlib.sha256(harness.read_bytes()).hexdigest(),
    "output_prefix_before": old_prefix,
    "output_prefix_after": str(fresh),
}, indent=2) + "\n")
print(fresh)
PY
)
/workspace/scratch/c2b093657c17/dev-venv/bin/python "$parity_replay/run_parity.py"
```

Run through a foreground execution session so cancellation reaches the owned process group. Keep sources fixed and retain incomplete/failed results. The new run records its own before/after identities and results; it does not replace this completed evidence.

For another machine or workspace, prepare the two recorded compiler revisions and their qualified native binaries separately. Adapt `ROOT` and `OLD_HOME` in the copied `summarize.py`, plus the copied harness's working-directory and output paths. Record those path-only changes and the resulting file hashes. Preserve the comparison logic and original archived files. Use the new run's actual binary hashes and source/input manifests; an adjacent checkout revision alone does not prove an existing binary's build provenance.
