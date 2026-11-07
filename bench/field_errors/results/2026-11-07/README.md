# Field-error prototype evidence, 2026-11-07

The parent [report](../../README.md) gives the interpretation, ranges and limits.
This directory contains the actual recorded data, including the initial setup
failure. It is not an assertion that the complete corpus has identical IR.

## Identities and validation

- `bootstrap-main.json` and `bootstrap-candidate.json` include pinned source/tool
  hashes, command, affinity, source stability, binary hashes and all six nonempty
  fixed-point witnesses. Their adjacent logs contain the original build output.
  These bootstrap wall times are validation observations, not a paired benchmark.
- `validation.json` records every later command and its return code, timing,
  environment and log hash. `full-corpus.log` retains the comparator's output.
  The comparator exited **1**, with 143 IR-only differences among 4,239 cases.
- `shared-inputs.json` contains all 105 runtime/library file hashes before/after
  for both checkouts. `path-only.diff` is the focused independent-home witness;
  the full corpus intentionally used one verified shared home.
- `attempt-1-path-setup*` preserves the preliminary path-witness failure: the
  imported example fixture was invoked without its required `.path` setup.
  The corrected attempt uses the repository's `tests/prepare_path.sh`.
- `native.log` records 262 passing JIT/AOT checks over 131 cases (all 129 affected
  executable program fixtures plus two controls). `program-gc.log` records 28
  passing checks over 14 focused cases with collection on every allocation.
  The compiler-GC witnesses and their exact IR hashes are in `validation.json`;
  `dry_field_error.py` preserves the generated first-table-during-dry witness.

## Accounting for all intentional differences

`corpus-cases.txt` records the complete input list. `irsame-capture.patch` is the
exact patch to the scratch copy of `tools/irsame.sh`: it retains the case list,
diagnostics, every changed old/new IR file and full report, without changing the
comparison or normalization logic. The full raw IR is retained at the scratch
capture path recorded in `validation.json`, rather than adding 169.7 MB to git.

`corpus-diagnostics.json.gz` preserves all raw old/new diagnostics. A separate
byte comparison found all 4,239 pairs identical (`diagnostic-audit.json`), so no
diagnostic normalization was needed. Shell exit statuses were checked by the
unchanged comparator; it does not persist each individual numeric status value.

`complete-raw-ir-diffs.patch.gz` contains all 143 complete textual IR diffs in
corpus order, with no identifier normalization. `fixture.diff` and
`secondary-inheritance.diff` are representative uncompressed copies.

`diff-audit.json` contains each changed case's old/new hashes, tag-indexed name
table, lookup count and structural checks. [audit_diffs.py](../../audit_diffs.py)
compares all other IR after narrow symbol/SSA/label renumbering; it is a separate
post-comparison explanation, never a replacement for the strict comparator or
native execution. The aggregate counts are 4,437 old `icmp`/`select` pairs and
2,096 new GEP/load pairs, not counts of single instructions.

To inspect compressed data:

```sh
gzip -dc complete-raw-ir-diffs.patch.gz | less
gzip -dc corpus-diagnostics.json.gz | python3 -m json.tool
```

To replay the structural audit against the retained capture:

```sh
python3 ../../audit_diffs.py /absolute/path/to/validation-directory
```

That directory must contain `report.json` and the old/new IR paths named by it.
When recreating the run elsewhere, update those capture paths in a separate copy
of the manifest. The raw original manifest is named `validation.json` here.

`bootstrap_runner_snapshot.py` and `validation_runner_snapshot.py` preserve the
local orchestration used for these commands. They contain the original absolute
tool/worktree/evidence paths, and the latter expects the prepared capture wrapper,
case list and shared-input manifest named in its source. They are execution
snapshots, not portable public command-line interfaces. The supported repeatable
compiler/build benchmark is `../../run.py`.

## Repeated timing cohort

`timings.json` stores every one of the 60 frontend and 36 native-build samples,
all min/median/max values, commands, source/tool/binary hashes, before/after
stability checks, IR counts and exact execution witnesses. `inputs/` contains
the six frozen sources. `*-warm-log.metrics.json` records the excluded separate
runtime-cache warmups. Every compiler stdout/stderr log was empty, as recorded
by its SHA256 in the raw samples. These runs had no failed or interrupted sample.

The cohort used five frontend samples and three native builds per revision/input,
CPU affinity 0 and alternating order. Native builds include frontend, LLVM and
linking after cache warmup; compiler preparation is excluded. The host is shared,
even though the local heavy validation queue was paused for the cohort. No-read
and sparse-read controls remain part of the report, including their unfavorable
medians and the sparse control's larger raw IR. Executable runs check behavior;
they do not measure generated-program throughput.
