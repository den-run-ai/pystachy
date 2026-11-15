# Production input equivalence after both proof repairs

Fresh read-only hashing verifies that final repair commit `0a2fe77a580106c197face4d2904be80e3f85dbc`, tree `107460d5f89bdcf37f2741b233eac0568d82604a`, has the same tracked production inputs as the evaluated `b0bda81ec2b9954c3c5e0f658c051439126a5c22`, tree `e027b37c888326e3d8a3e8b89522a6b397dcb86d`.

Both trees contain 10,493 tracked files. Exactly eight files differ, all within the two reviewed proof-tool repairs. The other **10,485 files have identical path, file mode, Git blob, and SHA256 inventories**. The published final tree also matches the frozen four-file storage repair exactly, and the earlier four repaired files retain their previously reviewed hashes.

| Verified input group | Files | Result |
|---|---:|---|
| Compiler and its shared cache helper | 60 | Byte and mode identical |
| Runtime and bundled native dependencies | 15 | Byte and mode identical |
| Library | 95 | Byte and mode identical |
| Differential corpus and helpers | 9,113 | Byte and mode identical |
| Benchmarks, examples, and ports | 692 | Byte and mode identical |
| Build and release configuration/scripts | 25 | Byte and mode identical |
| Release documentation | 21 | Byte and mode identical |
| Lean theorems and build inputs | 19 | Byte and mode identical |

These groups overlap; they are explicit views of the complete manifests, not a partition to sum. The compiler, library, test, benchmark, example, port, bundled-dependency, and workflow subtree object IDs also match directly.

The eight changed paths are `tools/check_lean_guards.py`, `tools/check_lean_storage.py`, `tools/lean_boundary/STORAGE.md`, `tools/lean_report.py`, `tools/test_lean_report.py`, `tools/test_lean_storage.py`, `tools/test_lean_storage_layout.py`, and `tools/test_lean_union_split.py`.

## Binding to prior execution evidence

**Bootstrap.** The original clean-tree receipt still identifies `b0bda81ec`, `make BOOTSTRAP_AOT_OPT=1`, return code zero, and 382.302 seconds. The compiler stage 1/2/3 IR hashes agree, as do runtime stage 1/2/3 hashes. The receipt and its linked hashes were checked and preserved. This comparison did not execute a new bootstrap.

**IR comparison.** All **4,771** recorded input hashes in both the IR identity and full analysis match both Git commits. All differential source files, helpers, sidecars, and recordings are also covered by the unchanged complete `tests` inventory. The input `tests/programs/io/symlink_main.py` retains its symlink bytes and mode; its resolved target `tests/linked/main_real.py` retains the recorded input SHA256. Each link step and resolved hash is retained in the input-binding manifest. Both the maintained oracle and the separate retention-only oracle still match their original identities. The existing comparison remains the alpha.2-to-`b0bda81ec` run with 562 differences and zero new rejections; no IR case was rerun here.

**Build costs.** All three recorded workload sources and arguments match: `bench/smoke/ml.py` (`numeric`, `20000`), `bench/smoke/text.py` (`json`, `6000`), and `bench/smoke/identity.py` (`float`, `6000000`, `123`). The original identity/report hashes and original compiler binary hash remain intact. These are three paired warm-runtime-cache native-build measurements per workload, with program cache disabled and one CPU. They do not measure program runtime or compiler-bootstrap speed. This comparison added no samples.

## Complete receipts

- `final-source-equivalence-b0-to-0a2f.json`: both commits/trees, exact eight-file diff, source-group hashes, original evidence bindings, and limits.
- `final-source-inventories.json`: complete before/after path, mode, Git blob, and SHA256 entries, plus explicit group membership. SHA256 `c94956752fa1eaed1eb91da8119df7c29b1f7edf310ab7a91a763710499385cc`.
- `final-source-input-bindings.json`: every one of the 4,771 recorded IR inputs and all three workload checks, including symlink resolution. SHA256 `319aab6dc50b58316c1ff0211c6df8f753b819a88f73054f1c7df3ad400c6f42`.
- `bind-final-source.py` and `final-source-binding.log`: reproducible read-only comparison and output.

The earlier four-file receipt and its manifests remain unchanged under `/workspace/scratch/980402bc01c4/evidence/lean/adapter-repair/`. Their current hashes are separately retained in the final receipt.

## Limits

The Git commit and proof-tool inputs differ. Earlier runs remain evidence about unchanged production code, not executions of the final repair commit. The fresh proof census must use the final immutable checker inputs; earlier errors and unknown-count results cannot be relabeled.

This receipt covers tracked objects and recorded inputs. It does not certify arbitrary untracked imports, environment, toolchain, ABI, cache, or machine state. It does not authorize bypassing `verification_bootstrap.py` commit, tracked-source, run, payload, or toolchain checks for strict artifact reuse.

Previously built binaries retain their original source provenance and may embed the `b0bda81ec` revision. They are not final-repair or eventual-main release artifacts. Unchanged `VERSION` bytes do not prove the version or provenance of public binaries, Docker layers, or PyPI packages; the exact eventual release commit and published artifacts still need the publication audit.

The explicit Lean build group was corrected to include `tools/lean_boundary/lakefile.toml`, increasing it from 18 to 19 files. The complete manifests already contained that unchanged file. Prior receipt/script/Markdown identities and the correction are retained in `source-binding-correction-history/omit-lakefile/` and `final-source-equivalence-correction.json`; the complete before/after entry arrays, eight-file diff, and all execution bindings are unchanged.
