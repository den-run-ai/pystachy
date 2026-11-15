# Constructor and numeric boundary continuation

Qualification for [PR #1495](https://github.com/den-run-ai/pystachy/pull/1495), stacked on
[PR #1493](https://github.com/den-run-ai/pystachy/pull/1493). The tested compiler source is
[`adf5a12a`](https://github.com/den-run-ai/pystachy/commit/adf5a12a147649d01018dd49c8167610812ada00),
whose complete tree is identical to local `2df26bde21451abb89cc487f57b0a5531c655b8d`.
The baseline is `adac7f4c88fd86ddaecbb889042b778c701b29ed`.
[Publication mappings](publication-map.json) preserve the full local/public commit and tree identities.

**Publication status: final qualification passed.** The final bootstrap, complete IR
comparison, native verification and canonical Lean report have passed. The final PR head is
[`1f9309a0`](https://github.com/den-run-ai/pystachy/commit/1f9309a0b6db9598ea16ff2b5195bd3e1aa30504),
whose complete tree matches local `3b03fed2a0d97eb1c1465262d576e18555218299`.
Its only change from the tested compiler source is the regenerated Lean report.
All local gates and final-head CI, Lint and Submission format have passed. Lint passed on
its second attempt in 707 seconds, with unchanged source, checks and time limits. The first attempt was
cancelled after 916 seconds during its final recording check and is included in the evidence. The historical
[provisional Lean checkpoint](lean-checkpoint-20261114T231015Z/README.md) remains explicitly
incomplete historical recovery evidence.

## Review and submission status

[PR #1495](https://github.com/den-run-ai/pystachy/pull/1495) is open, ready for review and unmerged,
stacked on PR #1493. The final body and ready-event Submission format checks passed with
head `1f9309a0` and base `adac7f4c` unchanged. Independent compiler, proof and evidence reviews
are clean within their stated scopes.

The automatic Codex review triggered when the draft was marked ready, but could not complete
because the account had reached its code-review usage quota. The
[bot's explicit quota message](https://github.com/den-run-ai/pystachy/pull/1495#issuecomment-6886418892)
and full review response are preserved with the final metadata. No additional review retry was
requested. This external review status is separate from the successful compiler and CI checks.

## Changes and scope

### Demanded constructor dependencies

A fixed-layout constructor can require another class's stable layout before a later inheritance
use requests it. The compiler now invokes its existing syntax-verified hierarchy dependency
discovery when a demanded constructor specialization fails, then retries in a fresh whole-program
pass. It does not retain speculative adapter dependencies or activate unused invalid descendants.
Variable-layout dependencies still reject.

Standalone, imported alias, module-qualified and quoted forms fail on both main `8049014` and
the PR #1493 baseline, then pass with this change. The state controls also check that one and
32 repeated constructions require the same two fresh compiler passes. The original preuse
rejection is replayed unchanged in the complete IR audit so moving it into the passing corpus
cannot hide its previous behavior.

### Optional numeric generator identities and cleanup

Optional integer and float yield channels carry the existing nullable numeric identity companion.
Aliases keep their original object; fresh numeric yields can leave the companion null until an
observer needs an object. This is separate from the optional channel's existing nullable payload
representation, which still allocates a representation box for a present numeric value.
Ordinary nontracking generators keep their previous layout. General unions and send/return
identity are not expanded.

Scalar numeric delegation into the matching optional channel is accepted. The optional integer
payload retains the documented checked 64-bit boundary even in a promoting-integer program.
Independent review found that a newly admitted wide integer could raise before the owned
delegate's cleanup path was installed. The final implementation reuses the existing conversion
cleanup: an owned child's `finally` executes before the wrapper handles the error, while a
borrowed child remains resumable.

Both new cleanup regression files fail against the pre-fix native compiler solely because the
owned child's `finally` is missing. The corrected version passes ordinary `next` without Any,
`send(None)` with tracking, both overflow signs, initial and later overflow, cleanup ordering,
repeated exhaustion and borrowed resumption. Independent probes also cover a wide value yielded
while handling `throw()`. Existing dynamic delegation is a positive control with identical
before/after output. These fixtures are explicit width deviations; CPython itself yields wide
integers without this storage-boundary exception.

### Companion growth/copy correspondence

The Lean model now covers reserve growth and contiguous slice/copy of initialized numeric-list
identity companions, preserving each selected identity and the final header-to-array-to-box
tracing edges for arbitrary valid live lengths. The adapter checks complete bounded C operations
and measured layouts against Clang; malformed growth/copy certificates reject.

Independent review exposed two holes in the previous physical-layout bridge. An anonymous union
could overlap `List.a` and `List.ids`; a padded `Slot` could change the real element stride.
Both were accepted previously. The final adapter independently requires distinct, aligned,
eight-byte header fields within the header, and checks the real slot size, value offset and width.
A native reserve probe demonstrates identity loss for the overlapping layout; both mutants now
reject while the live runtime accepts. The Lean kernel and axiom audit retain only the documented
standard axioms.

The proof still assumes initialized stable companions, valid nonoverflowing lengths/capacities,
fresh allocation, standard copy semantics, correct box materialization and source liveness during
allocation. It does not prove the concrete collector or a whole program's root/lifetime behavior.

## Validation

| Gate | Final result |
|---|---|
| Three-stage bootstrap | Passed: 940,952 compiler IR lines and 21,214 runtime IR lines, identical across all three stages |
| Full IR comparison | Passed: 4,649 final inputs plus the unchanged deleted-case replay; ten new corpus acceptances, one replay acceptance, no new rejections; all 4,633 surviving baseline cases unchanged |
| Native JIT/AOT and GC stress | Passed: 74 selected cases, 141 checks in each mode; normal/stressed list and boxing probes pass |
| Native contracts, recordings and lint | Passed: 2,715 IR/LLVM programs; 674 runtime entries, 70 exception classes and 193 runtime functions; 2,476 recordings, 136 deviations, 11 library copies; full lint |
| Canonical Lean report | Complete: all 2,612 programs, zero execution errors; clean source/executable provenance and passing canonical status |
| Strict promoting-integer storage corpus | Passed: all 182 programs, 18,658/18,658 obligations across 1,733 obligation functions; zero rejected, unsupported, execution errors or failed programs |
| Exact-head CI, Lint and Submission format | Passed on `1f9309a0`; CI run `43654295644`, Lint run `43654295641` attempt 2, all current format checks/statuses successful |

The verified native compiler SHA-256 is
`960326040b35ed71405c188ff4627d119925351dd084430c18a213ff416c31e2`.
The build used a temporary first-stage AOT tier of zero and a final compiler at tier two;
the bootstrap manifest records both, all 169 native input hashes and every fixed-point hash.
Toolchains are CPython 3.13.16, LLVM 18.1.3 and Lean 4.35.0 on Linux x86-64.

## Canonical proof coverage

The [generated report](https://github.com/den-run-ai/pystachy/blob/1f9309a0b6db9598ea16ff2b5195bd3e1aa30504/tools/lean_boundary/REPORT.md)
covers every one of the 2,612 requested programs with zero incomplete inspections. Within the
checked models, it proves all 2,618 dynamic payload reads, 86,194 checked accesses,
187 promoting-integer fit claims, 1,698 inline arithmetic uses and 18,658 storage obligations.
These are distinct obligations, not claims of whole-program semantic or collector correctness.

Unproved obligation totals remain unchanged from the previously committed report: 19 removed
null checks, 315 closed-union reads, 249 union-payload obligations, 237 field-initialization
obligations and 375 collector-scanning obligations. Rejected/unsupported function counts are
also unchanged. The complete report retains each category and its explanations.

The full run used the official clean-input resume path after interrupted worker executions.
Exactly two compiler-child execution-failure rows were removed from a derived checkpoint to
force actual full-scope recomputation; both passed. Original ledgers, failed attempts, the
transformation manifest and an isolated diagnostic replay are preserved. No ordinary unproved
or unsupported obligation was discarded, and no selected-scope result was grafted into the full
ledger. The generated report date is November 15 in the host's CET timezone; completion timestamps
are November 14 in UTC. The generated document was not manually edited.

## Allocation evidence

The committed [optional-generator workload and allocation record](https://github.com/den-run-ai/pystachy/tree/1f9309a0b6db9598ea16ff2b5195bd3e1aa30504/bench/generator_identity)
compare PR #1493 with the exact measured source tree published as
[`b77d496`](https://github.com/den-run-ai/pystachy/commit/b77d496547b733f4c121400ad1334f54aa33e1f8).
Each row is one instrumented AOT process with 20,000 optional float yields, including 1,250
missing values. Numeric checksums and missing-value counts match CPython.

| Consumer | Baseline allocation requests | Candidate allocation requests |
|---|---:|---:|
| Typed, fresh expression | 18,758 | 18,758 |
| Any, fresh expression | 37,510 | 37,510 |
| Typed, repeated source alias | 18,758 | 18,759 |
| Any, repeated source alias | 37,510 | 18,761 |

The repeated typed source needs one canonical identity box. The old repeated-Any case loses
identity and serves as a negative correctness control, rather than equivalent semantics. Its
managed-heap peak changes from 1,048,576 to 720,896 bytes; fresh typed consumption stays at
655,360 bytes. These are managed allocation requests and heap peaks, not RSS or live retention.
No timing measurement or general speedup claim is made.

The measured and final compilers emit byte-identical IR for the same benchmark input:
820 lines, SHA-256 `67436d5e09db39087db4d776ed679894e6782861a819b7b31805432cbeec1b1b`.
Before sharing a library home, all 111 non-compiler native/library/runtime resources were proved
identical. The recorded source inventories, commands and raw IR bind the measurements to the
final compiler without rerunning allocation or timing experiments.

## Evidence organization and remaining work

- `bootstrap/`: exact final source, binary, fixed-point hashes, command and complete build log.
- `ir/`: every case result, raw differences, exact normalization rules, source/binary inventories, replay scripts and an independently checked archive manifest.
- `native/`: final commands, source/binary hashes, selections, full gate logs and benchmark IR applicability.
- `lean/`: physical-layout negative controls, native mutant replay and proof review.
- `lean-final/`: complete canonical report, all program records, independent strict-storage results, frozen source/checker identities, recovery history and model assumptions.
- `ci-final/`: exact-head workflow, job, step, check/status and source-tree evidence.
- `final-metadata/`: final body/ready-state readbacks, successful metadata checks and the automated review quota response.
- `lean-checkpoint-20261114T231015Z/`: incomplete final-source Lean snapshot, immutable attempt/recovery history, and byte-preserving compression manifests.
- `cleanup-review/`: the confirmed review finding, deliberate pre-fix failures, repaired runs,
  controls and independent review with source hashes.
- `preliminary-40df/`: earlier completed checks and a clearly marked incomplete, superseded
  whole-report attempt. The first forkserver attempt could not create a Unix socket; the
  supported spawn mode was used afterward. No incomplete run is reported as complete.

The preserved recovery checkpoint records failed and interrupted attempts alongside completed
gates. Its final-source Lean history records the initial `BrokenProcessPool` interruption,
two later compiler children exiting with signal 9, the separately scoped replay and the
authorized whole-scope recovery. The termination causes were not established. No partial
report is labeled complete. Initial-head CI and Lint passed at `2a758d1`; that head precedes
the cleanup repair and does not qualify the final source.

Final whole-corpus Lean, strict-storage and exact-final-head remote-check evidence is complete. Research artifacts stay on this research branch and are not part
of the code PR.

Remaining work includes fixed-shape tuple and broader dict/set/general-union numeric identities,
static `Annotated` dependencies and stored-`Iterable` representation limits, and general alias,
allocation-liveness and collector proofs. The broader issues remain open. This continuation does
not enable default-on Any or change the runtime object model. The dependent PRs remain unmerged.
