# v0.5.0-alpha.3 premerge evidence

**UNFINALIZED TEMPLATE. Final qualification is not established here. Every `__REQUIRED_...__` value must be replaced with verified evidence before this becomes the accepted premerge record. Alpha.3 publication remains a later gate.**

This research branch preserves evidence for [release PR #1494](https://github.com/den-run-ai/pystachy/pull/1494), [enum repair #1496](https://github.com/den-run-ai/pystachy/pull/1496), [sparse-tag/report repair #1498](https://github.com/den-run-ai/pystachy/pull/1498), and [optional-tuple storage repair #1501](https://github.com/den-run-ai/pystachy/pull/1501). It is an evidence branch and must remain separate from main. The code at this research branch's root is historical; the pinned commits below identify the source used for each qualification result.

## Source identities and completed evidence

| Role | Commit | Tree |
|---|---|---|
| Published alpha.2 baseline | `80490143498d149d407343ba1cb7aedb1db2d2c5` | `717a8c9386ae9f5f6545cc3686a9e22282fc560c` |
| Retained bootstrap/IR/build-cost source | `b0bda81ec2b9954c3c5e0f658c051439126a5c22` | `e027b37c888326e3d8a3e8b89522a6b397dcb86d` |
| Completed census with strict-storage failure | `94f472d6de5350fc9481ecf3b9ec019d2ecdb4f2` | `51f6c150748b2d17945e4d1c6779d8080b6edd6a` |
| Reviewed final checker repair / fresh-census source | `0a2fe77a580106c197face4d2904be80e3f85dbc` | `107460d5f89bdcf37f2741b233eac0568d82604a` |
| Release branch after repair #1501 merge | `328b945f02788b296d9981d1b44706a2a0092255` | `107460d5f89bdcf37f2741b233eac0568d82604a` |

PR #1501 merged after all its checks passed. Its release-branch merge tree is identical to the reviewed repair tree; the census continues on **0a2f**, retaining that execution identity. Main remains at **80490143**. Integrated PR #1494 CI on **328b945f** is pending. [Merged-tree receipt](final-merged-tree-equivalence.json).

The [source-equivalence receipt](final-source-equivalence.md) verifies exactly eight changed proof-tool/documentation/test files, 10,485 unchanged tracked files, all 4,771 IR inputs including symlink resolution, all three build-cost workloads, and 19 unchanged Lean theorem/build inputs. Earlier executions retain their original source and binary identities; this comparison does not authorize bypassing strict bootstrap source/run checks.

- **Bootstrap:** fresh compiler and runtime fixed points at b0, three identical stages each. [Receipt](bootstrap.json), [log](bootstrap.log).
- **IR and diagnostics:** 4,771 cases, 562 changed records reviewed, zero new rejections or abnormal statuses; the original-input supplement covers 13 executions and 129 retained source/helper/sidecar files. This is bounded corpus compatibility evidence. [Full disposition](ir/full-disposition.md), [original inputs](ir/original-input-disposition.md).
- **Build costs:** three paired warm-runtime-cache native builds per workload across three workloads, with correctness checked. These measurements cover neither program runtime nor compiler-bootstrap speed. [Results](build-cost.md).
- **Native residual fixtures:** 24 retained JIT/AOT executions cover all 12 added residual fixtures; their synthetic CI merge tree equals b0. Runtime passes leave proof residuals unchanged. The complex-null deviation uses its explicit handwritten TypeError oracle. [Receipt](residual-native-coverage.md).
- **Storage repair:** the focused target proves 142/142 obligations across seven selected functions, with zero unknown/unsupported/rejected/error results; all 69 storage tests pass without skips and the old-adapter controls fail as expected. This fresh typed-only snapshot is distinct from the census snapshot. [Diagnosis](optional-storage-repair.md), [source review](reviews/optional-storage-root.md), [independent source review](reviews/optional-storage-independent.md).

## Historical census and required final gates

The completed **94f4** census covers 2,699 programs and 196 selected storage programs, retaining every alpha.2 program and selection. Its independent strict-storage gate fails: the optional tuple-key fixture has 8/8 counted obligations **plus three unsupported functions with unknown counts**. Consequently, its aggregate 25,682/25,682 known storage count is not strict-storage success. [Historical acceptance audit](lean-94/acceptance.json), [report](lean-94/report.md).

The fresh **0a2f** census has separate records and checker/input identities. Its final outcome is deliberately unresolved below.

| Required gate | Accepted final evidence |
|---|---|
| Full census completion, exit status, actual program/storage counts, records/report hashes, all nested errors and strict-storage verdict | __REQUIRED_FINAL_CENSUS_RESULT_COUNTS_HASHES__ |
| Immutable census commit/tree, clean inputs, Python/checker identities, and final target/unknown-count inventory | __REQUIRED_FINAL_CENSUS_SOURCE_AND_INPUT_BINDING__ |
| Every count decrease attributed, historical correspondence checked, extraction bound to final census | __REQUIRED_FINAL_DENOMINATOR_BINDING_RECEIPT_HASH_RESULT__ |
| Complete semantic/residual disposition and independent final evidence review, pinned to final hashes | __REQUIRED_FINAL_INDEPENDENT_REVIEW_RECEIPTS_AND_FINDINGS__ |
| Repair PR #1501 passed checks and merge: exact-head workflow links/hashes and review state | __REQUIRED_REPAIR_PR_FINAL_CHECKS__ |
| Integrated release head SHA/tree; every applicable workflow/job/step, skip reason, review thread and expected-head check | __REQUIRED_INTEGRATED_HEAD_SHA_TREE_AND_CI_REVIEW__ |
| Final premerge decision | __REQUIRED_FINAL_PREMERGE_DISPOSITION__ |

## Explicit proof limits

The completed 94f4 census records **542 rejected union reads and 409 associated unproved payload-bit obligations**, in 21 functions across nine added complex fixtures. Both counters share a joint verdict; each function is listed once under union. Review explains the first conservative-null-domain failure and does not prove later obligations. The final census must reconcile these residuals explicitly. [Complex review](complex-residuals.md).

`complex_values.py` adds **three instances of the existing copy memo-get GC model gap**, increasing the full known GC gap from 375 to 378; these differ from the three gaps in the focused enum check. The new Decimal fixture retains unsupported field inference with an unknown count. These limits remain visible in the final disposition. Bounded proof models, source review and runtime tests do not establish whole-compiler or collector correctness.

## History, corrections and later release gates

Preserve every attempt: the incomplete b0 census (1,865/2,699 programs, two inspection kills and 18 nested adapter errors); the 94f4 process exit -9 after 2,562 records and its identity-checked 137-record resume; the completed 94f4 strict-storage failure; intermediate repair refusals/rejections; and the separate fresh 0a2f census. Kill causes remain unproven. Retain previous correction versions/hashes, including the TOML receiver/AttributeError descriptions and the explicit Lean build-group correction. No header or earlier status is rewritten as a later success.

Archives retain member byte lengths and SHA256 manifests; [SHA256SUMS](SHA256SUMS) identifies published evidence. A separate publication receipt records the hash of that manifest, avoiding a self-referential README hash requirement. Alpha.2 baseline records retain their original uncompressed identity. Disclose archive exclusions and retain the identities/raw differences needed to reconstruct excluded large LLVM outputs and executables. The ready-triggered Codex review for #1501 failed because of the account quota ([attempt](https://github.com/den-run-ai/pystachy/pull/1501#issuecomment-6891447520), [quota result](https://github.com/den-run-ai/pystachy/pull/1501#issuecomment-6891447956)); it is separate from the successful independent agent source review and is not a completed review. Agent reviews are not human approvals.

After premerge qualification, merge through the expected-head path and require **all seven required workflows on the exact merged main SHA**. Native publication then requires actual Linux/macOS archive verification; Docker verification covers both amd64/arm64 manifests and layer bytes. The approved PyPI publisher follows the public native release. Its audit uses fresh isolated pip and uv installs of downloaded public packages; the local verifier installs retained public wheel bytes offline. Package, source, manifest and actual binary identities are checked separately. Reconfirm that GitHub, Docker and PyPI stable defaults remain **v0.4.0**. Record publication separately from this premerge decision.

Prepared with ChatGPT assistance. Finalization requires every placeholder above to be resolved, linked files and hashes validated, and the full final evidence independently reviewed.
