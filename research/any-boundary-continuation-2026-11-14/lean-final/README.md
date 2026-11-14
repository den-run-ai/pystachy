# Final Lean qualification

This bundle preserves the completed canonical Lean report, its full program ledger,
the strict promoting-integer storage results, execution identities, recovery history,
and independent review for the Any-boundary continuation in PR #1495.

The checked compiler and test source is local commit
`2df26bde21451abb89cc487f57b0a5531c655b8d`, published without source changes as
`adf5a12a147649d01018dd49c8167610812ada00`, tree
`30d991ebec23d92140381b4cd6fe6892a31b5a2b`. The report-only commit is
`9e23abd6cb5e20881ef730b5836a986bb723e93b`; the report is SHA-256
`d61511b4aba450ee2e01f981bb65f1644b373b7fd92ea3eebe0c9a58e71f6522`.
The strict-storage run retained the original checked source HEAD.

## Completed checks

The canonical report covers **2,612 of 2,612 requested programs**, with no
program-level inspection or checker execution failure in the completed ledger.
The report's source-status check passed for compiler, checkers, and corpus.
These results include model rejections and unsupported functions listed below;
completion does not mean every inventoried obligation was proved.

The strict storage gate independently accepted **all 182 selected programs**,
proving **18,658 of 18,658 obligations** in **1,733 obligation functions**. It
reported zero failed programs, rejected functions, unsupported functions, errors,
or unclassified functions. Its full totals also record 865 boundaries, 22,690
low-word uses, 746 tail reads, 60 stack-copy obligations, 120 stack-copy reads,
and 1,785 proof batches. The tool took 316.7 seconds (322.6 seconds wall time).

| Canonical check | Programs with obligations | Functions | Proved / inventoried | Rejected functions | Unsupported functions |
|---|---:|---:|---:|---:|---:|
| Dynamic payload reads | 293 | 1,171 | 2,618 / 2,618 | 0 | 0 |
| Unchecked list and dict accesses | 1,237 | 16,230 | 86,194 / 86,194 | 0 | 0 |
| Removed null checks | 944 | 13,240 | 136,424 / 136,443 | 4 | 0 |
| Closed-union reads | 277 | 2,216 | 6,636 / 6,951 | 31 | 7 |
| Union payload bits | 336 | 1,719 | 13,287 / 13,536 | Counted with union reads | Counted with union reads |
| Field initialization | 1,440 | 17,396 | 162,280 / 162,517 | 1 | 13 |
| Collector scanning | 1,696 | 26,488 | 191,632 / 192,007 | 37 | 3 |
| Promoting-int fit claims | 29 | 36 | 187 / 187 | 0 | 0 |
| Promoting-int inline arithmetic | 134 | 354 | 1,698 / 1,698 | 0 | 0 |
| Promoting-int storage | 169 | 1,733 | 18,658 / 18,658 | 0 | 0 |

The 182-program promoting-integer selection includes 13 programs with no storage
obligations. Function and obligation counts follow the canonical report's counting
rules; repeated library obligations and overlapping checks must not be summed into
a whole-program proof percentage. Full records retain every program result and
the unproved functions omitted from the report's abbreviated lists.

## Remaining proof gaps and assumptions

The report retains 19 unproved null-check removals, 315 union reads, 249 union
payload obligations, 237 field-initialization obligations, and 375 collector-scanning
obligations. The associated rejected and unsupported function counts are in the
table. [The report comparison](review/report-comparison.json) confirms these unproved
totals and function counts are unchanged from the previously committed report.

The unresolved null-check cases lack sufficient dereference facts. Union cases
include missing or insufficient member facts, absent declared source domains,
generator payloads without a member type, and payloads of no known member.
Field-initialization limits include bounded inference, block/instruction/fact
limits, unsupported construction escapes, and invalid adapter operands.
Collector-scanning cases include absent or mixed scanned-storage facts, graph
size limits, and invalid adapter operands. Every affected function and reported
reason is retained in the complete canonical ledger.

The new numeric-list companion model covers initialized stable companions,
identity stores, successful reserve growth, and contiguous slice/copy. It assumes
valid length/capacity relationships and indices, nonoverflowing C extents, fresh
destination storage, standard `memcpy` behavior, the semantics of called helpers,
and live source values during allocation. The C-to-model adapter, layout extraction,
pointer/word ABI, allocator size classes, and collector implementation remain
trusted. A final tracing chain does not prove source liveness during an allocation
or collection. Materialization's numeric value, promotion, iteration, stepped copies,
other list mutations, tuple/generator companions, and whole-program roots are outside
this model. These results do not justify removing roots, companions, or guards.

The broader report likewise does not prove parsing, inference, specialization,
general alias preservation, collector roots or lifetime, whole-pass optimization
equivalence, exception semantics, or LLVM lowering. The independent compiler review
also leaves general numeric send/return identity and arbitrary container aliases
outside this change. The model-specific trust boundaries are documented in the
[checked source's Lean overview](https://github.com/den-run-ai/pystachy/blob/adf5a12a147649d01018dd49c8167610812ada00/tools/lean_boundary/README.md).

## Interrupted attempts and recovery

The first attempt stopped with `BrokenProcessPool` after 1,383 complete records and
returned status 2. The first official resume later recorded two compiler children
terminating with signal 9, for `lib_argparse_required.py` and `lib_logging_config.py`.
Their termination causes were not established. That resume was interrupted through
its owned session with exit status 130.

The documented recovery retained the original full-corpus header and all 1,753
successful records byte for byte, removed only the two recorded execution failures
for official retry, and kept ordinary unproved or unsupported results. The final
official resume used one worker and the original inspection timeout. The separately
scoped argparse replay was preserved as history and was not inserted into the
canonical journal. Earlier journals, logs, statuses, exact failed records, commands,
and recovery manifests remain in this bundle and in the previous provisional
checkpoint; they have not been relabeled as successful runs.

The report displays 2026-11-15 because its generator used the host's CET local date;
its generation completed on 2026-11-14 UTC. The report-publication manifest records
both timestamps and the timezone. The generated report was not edited.

## Files and integrity

| Files | Contents |
|---|---|
| [Canonical report](canonical/REPORT.md) | Exact generated report bytes and all ten result rows |
| [Full canonical ledger](run/whole.resume2.jsonl.gz) | Every final program result and unproved function |
| [Full strict-storage results](run/storage.json.gz) and [summary](strict-storage-summary.json) | All 182 program records, function results, totals, and model limitations |
| [Final completion record](run/complete-qualification.json) and [freeze inventory](run/frozen-manifest.json) | Completion, status, identities, recovery, and immutable input/output hashes |
| [Run results](run/results.json) and [commands](commands.md) | Exact stage commands, return codes, timings, and execution context |
| `run/` history files | Original attempts, resumes, execution failures, replay, and recovery evidence |
| `review/` | Independent compiler and companion review, replay sources/results/logs, report comparison, and packaging review |
| [Inventory checks](inventory-checks.json) | Program-set and count checks recomputed from the preserved results |
| [Manifest](manifest.json), [checksums](SHA256SUMS), and [verification tool](tools/package_final_lean.py) | Exact package membership, content identities, modes, and decompression checks |

Files larger than 50,000 bytes are stored as deterministic gzip streams with zero
mtime. The manifest records every source path, original size and SHA-256, stored
size and SHA-256, Git blob SHA, mode, and encoding. Compression changes only storage:
`gzip -dc` recovers the exact original bytes. Reproducible executables and caches are
excluded. The immutable completion and identity inventories are retained alongside
the results.

With Python 3.13, verify the package without rerunning compiler or Lean checks:

```sh
python3.13 tools/package_final_lean.py verify .
sha256sum -c SHA256SUMS
```

Exact stage commands, environment, tool versions, source and checker identities,
and return codes are preserved in the results and identity manifests. The execution
orchestration used Python stdin; no standalone final-Lean orchestration script was
created. The report and storage tools are versioned in the pinned source tree.
The bundled packaging tool only copies and verifies frozen evidence.

The canonical report is preserved byte for byte. Its relative documentation links
refer to the source repository's `tools/lean_boundary` directory. This bundle makes
no claim about the final PR head's CI state; that evidence is tracked separately.
