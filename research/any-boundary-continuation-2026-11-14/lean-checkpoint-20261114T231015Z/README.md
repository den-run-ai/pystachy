# Provisional Lean recovery checkpoint

**Status: incomplete.** This checkpoint preserves 1,776 complete program records
from the 2,612-program canonical Lean inventory, captured at 2026-11-14 23:10:15 UTC.
It is not a completed canonical report, a strict storage result, or final-head CI
qualification. The source is local `2df26bde21451abb89cc487f57b0a5531c655b8d`,
published unchanged as `adf5a12a147649d01018dd49c8167610812ada00`, with tree
`30d991ebec23d92140381b4cd6fe6892a31b5a2b`.

The final bootstrap, complete IR comparison, focused native JIT/AOT and GC tests,
runtime probes, IR/runtime contracts, recordings and lint have already passed.
Their complete evidence is linked from the [qualification index](../README.md).
The canonical Lean report, the 182-program strict storage gate and checks on the
final PR head remain pending.

## Preserved history

The initial whole-scope report stopped with `BrokenProcessPool` after 1,383 complete
records and returned status 2. No inspection/checker error was recorded in that
first journal; the abrupt worker termination's cause was not established.
The first official resume retained those records and later recorded two compiler
children exiting with signal 9, for `lib_argparse_required.py` and
`lib_logging_config.py`. The cause of those terminations is also unknown.

That resume was interrupted through its owned session. The recovery manifest
records the interruption, the two exact failed execution records, and retention
of all 1,753 successful records byte for byte. The next official resume uses the
original whole-corpus inventory and a single worker. Ordinary unproved or
unsupported results were retained. The separately scoped successful argparse
replay was preserved as evidence and was not inserted into the canonical journal.

`history/` contains the unchanged original journals, failures, interruption and
recovery manifests, replay output, commands, and source/executable identities.
The orchestration ran through Python stdin; there is no standalone final-Lean
runner file. Exact make/Python stage commands are recorded in the preserved
results, statuses and recovery manifest, and the report implementation remains in
the pinned source tree.

## Snapshot and integrity

`snapshot/manifest.json` is the unchanged capture manifest. The frozen snapshot
has 1,776 unique program records, no recorded execution errors, and original
SHA-256 `7c73d89229af864e11c714b8104256cf7b09b40d02c0ae5d2393ebbcc790b687`.
The absence of execution errors in this partial snapshot is not a whole-corpus
completion or proof claim.

Files larger than 50,000 bytes are stored as deterministic gzip streams. Their
decompressed bytes are identical to the frozen originals. The
[checkpoint manifest](checkpoint-manifest.json) records every original and stored
size and SHA-256, source path and compression method. Use `gzip -dc` to recover
the original bytes before checking the original hash or using an official resume.
The manifest does not describe a new or reduced verification scope.

The live second-resume journal, active log, mutable run status/results, future
strict-storage output, caches and reproducible ELF files are excluded. No running
report inputs or history files were changed to create this checkpoint.
