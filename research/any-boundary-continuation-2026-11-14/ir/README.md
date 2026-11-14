# Static/Any follow-up: final retained IR audit

**No new rejections, no meaningful changes to existing rejection diagnostics, and no meaningful IR changes in the 4,633 surviving baseline corpus cases.** All their differences reduce to independently checked compiler installation paths. The exact removed constructor-rejection source was replayed separately and now compiles successfully.

This checkpoint includes the correction for checked integer-to-optional-integer delegation cleanup, plus the ordinary and protocol regression fixtures added after review of the preliminary `40dfd158` checkpoint. That preliminary audit and its evidence remain separate. This final audit compares native compiler acceptance, diagnostics, and emitted LLVM IR; native execution, GC stress, and Lean validation have separate evidence.

## Source and binary identities

The baseline is `adac7f4c88fd86ddaecbb889042b778c701b29ed`. The final audited and compiled candidate is local commit `2df26bde21451abb89cc487f57b0a5531c655b8d`, published with the identical Git tree as [adf5a12a147649d01018dd49c8167610812ada00](https://github.com/den-run-ai/pystachy/commit/adf5a12a147649d01018dd49c8167610812ada00). That tree is `30d991ebec23d92140381b4cd6fe6892a31b5a2b`.

| Compiler | Native binary SHA-256 | Build source |
| --- | --- | --- |
| Baseline | `5dc9973d3a0ff8b79b8ae9ba2ca7d81347b460c8de0a015d6b2acd898c2ebf6e` | `d68c9837ccad11e46b29a8955cc125c1a33cb77b`; native inputs verified byte-identical to `adac7f4` |
| Candidate | `960326040b35ed71405c188ff4627d119925351dd084430c18a213ff416c31e2` | The exact audited `2df26bde` source, with all 169 bootstrap input hashes rechecked |

The audit harness uses CPython 3.13.16. The native compilers use LLVM 18.1.3. Both three-stage compiler and runtime fixed points were checked against their manifests; the final candidate fixed points contain 940,952 and 21,214 lines respectively. The final native binary equals the recorded stage-two native artifact.

The baseline native-input equivalence check covers the compiler entry points, `src`, `lib`, `runtime.c`, `runtime.py`, `ryu`, `mpz`, `lljit.c`, version metadata, and the pinned Python-version file. The final bootstrap manifest additionally records 169 individual native input hashes, all checked against both the working source and the frozen archive before this run. The full archived source inventories are in `source-identities.json.xz`, including every source, imported helper, sidecar, and other tracked file. Frozen homes contain only those archived files, two recorded revision files, and the verified native binary. The complete file sets and all hashes were verified before and after the run.

`publication-map.json` records the local/public commit mappings. The audited checkpoint is the exact source tree above; later canonical-report or provenance-only commits do not change this run's identity.

## Coverage and result

The baseline has 4,634 IR-oracle inputs; the final candidate has 4,649. The difference is 16 added paths and one removed path, with **zero changed source bytes in surviving case paths**. The canonical executable/rejection corpus from `tests/corpus.sh` contains 4,531 baseline and 4,546 final cases. The IR oracle additionally includes the compiler, runtime, benchmarks, and IR-only probes.

Both native compilers ran every final input. Comparison 4650 reads the exact original bytes and sidecar of `tests/errors/classes/constructor_dependency_preuse.py` from the baseline frozen home. Its shared import fixture, `mods.constructor_dependency`, is unchanged from the baseline.

| Classification | Final corpus | Original deleted-source replay | Total |
| --- | --- | --- | --- |
| Same status and IR; diagnostics equal under the upstream source-location normalization | 4351 | 0 | 4351 |
| Independent library installation paths only | 282 | 0 | 282 |
| Separately reviewed sys installation-prefix constants | 2 | 0 | 2 |
| Rejection becomes successful compilation | 10 | 1 | 11 |
| Intended IR changes in added optional-generator fixtures | 4 | 0 | 4 |
| **Total** | 4649 | 1 | 4650 |

There are no acceptance-to-rejection changes. 2,705 inputs compile in both compilers; 11 change from exit 1 to exit 0; 1,934 retain exit 1. Of the 4,351 unchanged comparisons, 56 have raw diagnostic differences already normalized by the upstream oracle. All 70 raw diagnostic differences among retained rejections consist only of library installation paths.

The upstream comparison rules report **299 differences**, so the raw exit status is **1**. This expected nonzero status is preserved. Classification explains all 299 differences: 284 path differences, 11 acceptance gains, and 4 intended IR changes. The retaining wrapper increases the report limit and retains evidence without relaxing the upstream comparison.

The run used two workers. Inherited `PYSTACHY_*`, `PYTHONHOME`, and `PYTHONPATH` variables were cleared; `command.json` records the exact command and overrides. Each compiler loaded its own frozen `lib/`, and all library hashes are equal between those homes. Both compilers consume the same frozen candidate source, sidecars, and test helpers for each final case. The bracket-path fixture is copied from the frozen source by the upstream preparation helper. The comparison wrapper and execution script also remained unchanged throughout the run.

## Every acceptance gain

All 10 final-corpus gains are added regression fixtures. Successful candidate compilations emit no diagnostic.

| Final-corpus path | Baseline blocker removed |
| --- | --- |
| `tests/programs/classes/constructor_dependency_preuse.py` | Fixed-layout `Options` was rejected as a class template while specializing standalone `NestedErrors` before hierarchy use. |
| `tests/programs/classes/constructor_dependency_preuse_alias.py` | The same fixed-layout dependency failure through an imported class alias. |
| `tests/programs/classes/constructor_dependency_preuse_qualified.py` | The same dependency failure with a module-qualified annotation. |
| `tests/programs/classes/constructor_dependency_preuse_quoted.py` | The same dependency failure with a quoted imported annotation. |
| `tests/programs/classes/constructor_dependency_standalone.py` | The same dependency failure without a later hierarchy use. |
| `tests/programs/inference/dynany_identity_generator_optional_protocol.py` | Optional-float delegation was rejected when the delegated generator yielded a nonoptional float. |
| `tests/programs/inference/dynany_identity_generator_optional_widen.py` | Optional-integer delegation was rejected when the delegated generator yielded a nonoptional integer. |
| `tests/programs/numbers/python_int_generator_optional_identity.py` | The optional-integer delegation failure also occurred with Python-integer storage. |
| `tests/deviations/python_int_optional_generator_cleanup.py` | Optional-integer delegation was rejected; the new fixture also exercises owned/borrowed cleanup and exception handlers during checked narrowing. |
| `tests/deviations/python_int_optional_generator_cleanup_protocol.py` | The same optional-integer delegation failure under the generator protocol, with owned/borrowed cleanup and exception-handler coverage. |

Separately, **`tests/errors/classes/constructor_dependency_preuse.py`**, unchanged from the baseline archive, switches from its class-template diagnostic at line 6 to exit 0. Retained index **4650** preserves this original input despite the fixture's move into the program directory.

The other two added cases retain identical results: `constructor_dependency_preuse_speculative.py` compiles, and `constructor_dependency_preuse_variable.py` rejects its variable-layout dependency. Full paths and hashes are in `case-results.jsonl`.

## Every meaningful accepted-IR change

All 4 cases below are added in the candidate. No surviving baseline case has a meaningful IR change.

| Path | IR lines, baseline → candidate | Explanation |
| --- | --- | --- |
| `tests/programs/inference/dynany_identity_generator_optional.py` | 2,301 → 2,684 | Identity companions propagate through optional numeric yields, direct/dynamic iteration, narrowing, and forwarding. |
| `tests/programs/inference/dynany_identity_generator_optional_fresh.py` | 1,857 → 2,302 | Companions distinguish retained aliases from fresh equal-valued yields and propagate through next adapters. |
| `tests/programs/inference/dynany_identity_generator_optional_scope.py` | 815 → 914 | Imported optional numeric producers and consumers preserve companions across their module boundary. |
| `tests/deviations/python_int_optional_generator_width.py` | 1,269 → 1,390 | Optional integer payloads and identity companions use the width-correct conversion paths during direct and delegated yields. |

`meaningful-ir-functions.json` identifies every changed function. No function is added or removed in these cases. Changes outside function bodies are required numeric-box helper declarations or their ordering. Complete old/new IR and raw diffs are retained.

## Exact path normalizations

Raw output is preserved. Every case record includes statuses, source/IR/message hashes, complete raw diagnostics, upstream-normalized diagnostics, the raw oracle report, and its classification. The two frozen home names have equal byte lengths. Every source file was checked not to contain either frozen-home path as literal content, and every library source hash matches between homes.

1. **282 library-path-only comparisons.** Replacing the exact byte prefixes `/workspace/scratch/1a96cd11db0d/ir-audit-final/home-old/lib/` and `/workspace/scratch/1a96cd11db0d/ir-audit-final/home-new/lib/` with the same marker makes the complete old/new IR and diagnostics equal, with equal exit statuses. This covers 268 successful compilations and 14 retained rejections. Complete raw diffs are retained. No arbitrary filename, line number, diagnostic text, or LLVM instruction is normalized.
2. **Two separately reviewed installation-prefix comparisons.** `tests/programs/library/lib_gettext.py` uses `lib/gettext.py:62`, where `sys.base_prefix` contributes the default locale directory. `tests/programs/library/sys_prefix.py` directly reads the four `sys` installation prefixes. `src/pystachy_compiler/builtins.py:145–148` emits `self.prefix` for those attributes. Their complete diffs contain only that installation-prefix constant, plus a library-location string in the gettext case. Exact frozen-home-prefix replacement makes the complete IR equal. This broader replacement is permitted only for these two named cases.

The 14 rejection diagnostics outside the upstream oracle's conservative location normalization are:

- `tests/errors/inference/any_lru_cache.py`
- `tests/errors/library/lib_copy_callable_field.py`
- `tests/errors/library/lib_copy_deep_order.py`
- `tests/errors/library/lib_copy_getstate.py`
- `tests/errors/library/lib_copy_library_base.py`
- `tests/errors/library/lib_copy_library_class.py`
- `tests/errors/library/lib_csv_namedtuple_row.py`
- `tests/errors/library/lib_datetime_strptime.py`
- `tests/errors/library/lib_datetime_utcnow.py`
- `tests/errors/library/lib_enum_missing_result.py`
- `tests/errors/library/lib_functools_lambda.py`
- `tests/errors/library/lib_functools_unannotated.py`
- `tests/errors/library/lib_itertools_starmap_list.py`
- `tests/errors/library/lib_statistics_kde.py`

Complete raw diagnostics are retained; exact library-prefix replacement makes each pair equal. There are no changed diagnostic meanings.

## Artifact contents and checks

- `summary.json`: counts and source/build/publication identities.
- `case-results.jsonl`: all 4,650 case records with statuses, hashes, diagnostics, modes, import paths, and classifications.
- `source-identities.json.xz`: full source inventories and binary identities.
- `raw-changed-cases.tar.xz`: complete retained files for all 299 raw differences under `raw/<index>/`. Both old/new IR files are included where emitted. Unchanged IR is represented by equal hashes.
- `raw-files.json`: SHA-256 and size of every uncompressed archive member.
- Bootstrap manifests/log, `source-rechecked.json`, and `publication-map.json`: source/build/publication correspondence.
- `scripts/`: the exact audit, classifier, and function-difference extraction scripts, preserving their original workspace paths.
- `SHA256SUMS`: checksums for every artifact except the checksum file itself.
- `verify_bundle.py`: verifies file checksums, archive completeness/content, case identities/statuses, and every path-only classification without invoking a compiler or extracting archived files.

Run `python3 verify_bundle.py` from this directory. The verifier uses only Python's standard library.

## Replay with fresh builds

Use the project-pinned CPython 3.13.16 and LLVM 18.1.3. Set `compiler_py`, `llvm_bin`, `repo_dir`, and `audit_dir` to explicit local paths. Build in isolated checkouts, then use fresh equal-length archived homes with independent binaries and libraries.

```sh
git -C "$repo_dir" worktree add --detach "$audit_dir/build-old" adac7f4c88fd86ddaecbb889042b778c701b29ed
git -C "$repo_dir" worktree add --detach "$audit_dir/build-new" adf5a12a147649d01018dd49c8167610812ada00
PYSTACHY_LLVM="$llvm_bin" PYSTACHY_JOBS=2 make -C "$audit_dir/build-old" PY="$compiler_py"
PYSTACHY_LLVM="$llvm_bin" PYSTACHY_JOBS=2 make -C "$audit_dir/build-new" PY="$compiler_py"
mkdir -p "$audit_dir/home-old" "$audit_dir/home-new"
git -C "$repo_dir" archive adac7f4c88fd86ddaecbb889042b778c701b29ed | tar -x -C "$audit_dir/home-old"
git -C "$repo_dir" archive adf5a12a147649d01018dd49c8167610812ada00 | tar -x -C "$audit_dir/home-new"
cp "$audit_dir/build-old/pystachy" "$audit_dir/home-old/pystachy"
cp "$audit_dir/build-new/pystachy" "$audit_dir/home-new/pystachy"
```

Run the standard final-corpus oracle and the original-source replay with a sanitized environment:

```python
import os
from pathlib import Path
import subprocess

audit_dir = Path("/absolute/path/to/audit-replay")
llvm_bin = "/absolute/path/to/llvm-18/bin"
old_home = audit_dir / "home-old"
new_home = audit_dir / "home-new"
env = {k: v for k, v in os.environ.items()
       if not k.startswith("PYSTACHY_") and k not in ("PYTHONHOME", "PYTHONPATH")}
env.update(PYSTACHY_JOBS="2", PYSTACHY_LLVM=llvm_bin, LC_ALL="C")
command = ["sh", "tools/irsame.sh", str(old_home / "pystachy"), str(new_home / "pystachy")]
subprocess.run(command, cwd=new_home, env=env, check=False)
subprocess.run(command + [str(old_home / "tests/errors/classes/constructor_dependency_preuse.py")],
               cwd=new_home, env=env, check=False)
```

The first command compares 4,649 inputs and the second compares one. Both are expected to report differences. `command.json` preserves the original full retained invocation; `scripts/retaining-irsame.sh` preserves the instrumented upstream oracle. Its additions select the frozen working directory, increase the display limit, and record/retain evidence.
