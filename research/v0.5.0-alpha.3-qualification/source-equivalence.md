# Production source equivalence for the Lean repair

The repair commit `94f472d6de5350fc9481ecf3b9ec019d2ecdb4f2` has byte-identical tracked compiler, runtime, library, test and benchmark inputs to the previously evaluated `b0bda81ec2b9954c3c5e0f658c051439126a5c22`. Only the guard adapter, census reporter and their two test files differ. This supports applying the prior results as evidence about unchanged production code; none of those runs is relabeled as a run of the repair commit.

| Input group | Files | Byte/mode inventory |
|---|---:|---|
| all unchanged tracked files | 10489 | Identical |
| benchmark examples ports | 692 | Identical |
| build release configuration | 25 | Identical |
| compiler | 60 | Identical |
| library | 95 | Identical |
| runtime | 15 | Identical |
| test corpus and helpers | 9113 | Identical |

## Existing evidence preserved

- Bootstrap: original commit `b0bda81ec`, command `make BOOTSTRAP_AOT_OPT=1`, exit 0 in 382.302 seconds; the original recorded compiler and runtime fixed-point hashes remain attributed to that run.
- IR comparison: all 4,771 recorded input hashes match both commits, as does the maintained oracle. The symlink input `tests/programs/io/symlink_main.py` retains both its link contents and the resolved `tests/linked/main_real.py` content hash. The existing alpha2-to-alpha3 comparison has 562 differences and zero new rejections; full dispositions remain in the separate IR review.
- Performance: the existing passed report remains tied to its recorded binary and `b0bda81ec`; all three benchmark source hashes match both commits. No measurements were repeated here.

The JSON receipt records both trees, all changed-file hashes, source-group manifest hashes, unchanged subtree objects, input-hash checks and original evidence hashes. The companion inventories preserve every compared path, file mode, Git blob and SHA-256.

## Limits

- Only tracked Git objects and recorded input hashes are compared; this does not independently certify arbitrary untracked imports, environment, toolchain or machine state.
- The Git commit and four proof-related tool files differ, so whole-checkout source identity differs even though production code is unchanged.
- Do not bypass tools/verification_bootstrap.py commit, tracked-source, run identity, payload or toolchain checks; this receipt does not authorize strict artifact reuse across commits.
- No bootstrap, IR comparison, benchmark, native/GC suite or full Lean census was rerun for this receipt.
- Fresh proof qualification is required because the guard adapter and completion reporter changed; old Lean counts/errors are not relabeled as repaired results.
- CI/release gates must still be tied to their exact evaluated release commit. Existing binaries retain b0bda81ec source provenance and may embed that revision; they are not 94f472d6 or eventual-main release artifacts.
- VERSION bytes are unchanged; that does not establish actual binary version or eventual GitHub/Docker/PyPI artifact provenance.
