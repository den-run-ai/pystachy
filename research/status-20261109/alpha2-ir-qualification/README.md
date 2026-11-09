# Alpha.2 IR qualification of #1187: passed

Snapshot: 2026-11-09, about 14:10 UTC. This is research and validation evidence; keep it off main.
It completes the gate that stopped the earlier attempt
([final evidence at 778b8f77](https://github.com/den-run-ai/pystachy/blob/778b8f770e59c6a920febcf50d5ab6c08ffe84de/research/status-20261109/alpha2-qualification/README.md),
on `research/alpha2-qualification-20261109`).
That attempt's resume condition was a byte-exact comparison of the full corpus, including
diagnostics and exit statuses, in a reliable environment, with each compiler's own inputs and
#527 accounted for.

## Verdict

[#1187](https://github.com/den-run-ai/pystachy/pull/1187) at head `52da3b8ffd394f124697dfaadb0d0e55108866a7` (tree `0e84b32e`)
against main `d6b9b3f18bc5adf0da021da46f74c9837be0c604`: 4,354 of 4,354 corpus cases give the
same IR, diagnostics and exit status. The only differences under the ordinary oracle are #527's
checkout paths.

- **Ordinary oracle.** `make irsame REF=d6b9b3f1`, unchanged, reports 264 of 4,354 differing
  ([logs/irsame-official.log](logs/irsame-official.log)). This matches the earlier attempt.
  - 251 IR cases have 307 differing line pairs. All are string constants holding the home's real
    path: 305 ImportError texts and 2 `sys.prefix` values.
  - 13 rejections differ only in how they spell `build/ref/lib/` and `lib/` in `FILE.py:LINE`
    locations.
  - There are no exit-status differences ([classification.tsv](classification.tsv): all 264 are
    category a, path-only).
- **Same-commit baseline.** Main against main with homes at two equal-length paths shows the same
  264 cases and the same lines once paths are masked
  ([results/lines-equivalence.txt](results/lines-equivalence.txt)).
- **Same path, no normalization.** Each compiler ran with its own complete home at one real path,
  first main (run A) and then #1187 (run B). Raw IR, messages and statuses were byte-identical for
  4,354 of 4,354 cases ([results/same-path-main-vs-pr.txt](results/same-path-main-vs-pr.txt),
  [results/same-path-cmp.txt](results/same-path-cmp.txt)).
- **Integrity.**
  - Inventories of the checkout and both homes were unchanged before and after every run
    ([logs/runB.log](logs/runB.log)).
  - Every run completed all cases in corpus order.
  - Main's outputs were identical across two full passes, and a 441-case subset was identical
    across three passes ([results/subset-reruns.txt](results/subset-reruns.txt)).

The environment was Linux x86-64 with 4 vCPUs, the checkout and homes on ext4, and LLVM 18.1.3.
The hosted bootstrap ran on CPython 3.13.18. Both compilers were built with `make` and reached the
compiler and runtime fixed points. The work was done by a Claude Code subagent and checked by the
coordinating session; [commands.txt](commands.txt) and [counts.txt](counts.txt) list every step.

## Coordinator checks

Checks made independently of the agent's analysis scripts:

- **Per-case records.** Recomputed from the per-case sha256 records in [runs/](runs/):
  - Main and #1187 at the same path are equal for 4,354 of 4,354 cases.
  - Main's two passes are equal for all 4,354.
  - No exit status differs, and no case produces IR from only one compiler.
  - There are 2,469 IR outputs and 1,885 rejections.
  - The cases the oracle reported are exactly the 264 in `classification.tsv`.
- **Homes.** Every tracked file in the main home (9,414 blobs) and the #1187 home (9,415 blobs)
  matched its commit's tree. Binary sha256s were `92f4a6f3…` for main and `0f431daa…` for #1187,
  and `VERSION` read `v0.4.0-alpha.1` and `v0.4.0-alpha.2`.
- **Live GitHub.** #1187 is still at head `52da3b8f` on base `d6b9b3f1`, draft, with mergeable
  state clean. It has 22 check runs: 21 succeeded, and DCO was skipped as expected for a
  same-repository PR. Codex reviewed this head without findings, and there are no review threads.

## Merging with #1188 and #1189

Notes are in [merge-1188-1189.txt](merge-1188-1189.txt).

- #1187 merges cleanly with #1188.
- With #1189 there are two small textual conflicts: `driver.py`, where #1189 renames `mcjit` to
  `llcobj`, and one launch row in `tools/program_cache_probe.py`. The file gives resolutions.
- If either lands first, #1187's head changes. The release notes then need the edits listed there,
  and this qualification must be rerun on the new head against the new main. A corpus pass takes
  about 2–3 minutes here.

## Not covered

- Not run: `irsame-py`, the oracle's `--check` mode, other platforms or LLVM versions, and builds
  of the merged trees.
- The IR oracle does not exercise #1187's `runtime.c` or `pystachy run` launch changes; CI and the
  earlier focused probes cover those.

## Files

| Path | Contents |
|---|---|
| [counts.txt](counts.txt), [commands.txt](commands.txt) | Results and the exact commands |
| [classification.tsv](classification.tsv) | All 264 oracle differences |
| [results/](results/) | Per-run summaries, every differing IR line in O2 (`O2-lines.txt`), message substitutions, reruns |
| [runs/](runs/) | sha256 of every output, both compilers, for runs A and B (gzipped JSON) |
| [logs/](logs/) | Build logs and run logs with inventory checks |
| [scripts/](scripts/) | The harness: `irsame-keep.sh` is `tools/irsame.sh` plus the changes in `irsame-keep.diff` |
| [pr1187-comment-draft.txt](pr1187-comment-draft.txt) | A draft for #1187; not posted |

The raw IR archives (825 MB) stayed in the session's scratch directory and are not kept.
