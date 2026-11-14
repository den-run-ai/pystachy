# Alpha.2 exact-main qualification evidence

This package records the completed publication gate for Pystachy
`v0.5.0-alpha.2` at main commit
`80490143498d149d407343ba1cb7aedb1db2d2c5`, tree
`717a8c9386ae9f5f6545cc3686a9e22282fc560c`.

## Complete workflow gate

All seven applicable main-push workflows completed successfully on attempt 1.
Complete pagination accounted for seven workflow runs and 132 terminal commit
check runs: 131 successful jobs and one expected PR-only CI skip.

| Workflow | GitHub run | Successful jobs | Expected skips | Longest job |
|---|---:|---:|---:|---:|
| CI | [43624131788](https://github.com/den-run-ai/pystachy/actions/runs/43624131788) | 73 | 1 | 619 s |
| Installation | [43624131831](https://github.com/den-run-ai/pystachy/actions/runs/43624131831) | 7 | 0 | 561 s |
| Lint | [43624131842](https://github.com/den-run-ai/pystachy/actions/runs/43624131842) | 1 | 0 | 670 s |
| Packages | [43624131798](https://github.com/den-run-ai/pystachy/actions/runs/43624131798) | 1 | 0 | 327 s |
| Performance smoke | [43624131736](https://github.com/den-run-ai/pystachy/actions/runs/43624131736) | 1 | 0 | 626 s |
| Coverage | [43624131838](https://github.com/den-run-ai/pystachy/actions/runs/43624131838) | 23 | 0 | 621 s |
| Variants | [43624131795](https://github.com/den-run-ai/pystachy/actions/runs/43624131795) | 25 | 0 | 379 s |

CI, Installation, Lint and Packages are the documented publication gates. The
other three are separate source-relevant workflows and were also required to
finish for this qualification. Every executed job was below the 15-minute cap.
Full native and alternate-configuration CI ran on both Linux architectures;
the skipped row is guarded specifically for pull-request events.

The downloaded x86-64 and AArch64 aggregate reports each pass **58/58 checks
across 35 groups**, including **192/192 runtime-cache checks**. Their source
hashes, exact corpus, check names and group coverage were revalidated. Both
report 4,476 canonical cases, 7,272 full-suite checks and 4,722 single-mode checks.
Exact-main strict storage accepted all **175 programs and 18,582 obligations**.
Bootstrap qualification preserved every compiler/runtime fixed-point witness
and produced identical final compiler bytes through the O1/O2 paths.

## Fresh paired runtime/build smoke

The fresh Performance artifact compares alpha.1 main
`a73c56c92f3aad4b490307a5d1b882e487a57f55` with this alpha.2 commit.
Independent audit verified its ZIP, provenance, workload hashes and raw samples.
All **49 comparisons are `ok`**, with no warning or unconfirmed outcome.
Five warmed source builds were 23.5–82.3% shorter. Runtime median changes varied:

| Metric | Observed change range |
|---|---:|
| JIT process time | -0.8% to +2.0% |
| JIT loop time | -0.9% to +4.7% |
| AOT process time | -5.6% to +4.7% |
| AOT loop time | -6.4% to +4.4% |

These are eleven bounded workloads on one shared CI host, using three
interleaved pairs, warmed runtime caches and disabled program caching. They do
not establish a general execution-speed improvement. This artifact does not
measure executable size or peak RSS.

### Separate bootstrap observation

The same run's single sequential compiler-bootstrap pair took
**155.481 → 162.397 seconds (+4.4%)**. This is one observation per revision,
without repetitions or confirmation. It remains separate from the 49 paired
smoke comparisons and from the warm application-build measurements below.

## Bounded warm-build memory and size comparison

Three alternating pairs per workload used the final qualified native compilers,
exact release-source homes, one CPU, private warmed runtime caches, LLVM 18.1.3,
CPython 3.13.16 and disabled program caching. Every one of the 24 warmup/measured
executables matched the pinned CPython output. Independent audit recomputed all
counts, medians and hashes.

| Workload | Build seconds, alpha.1 → alpha.2 | Peak RSS KiB, alpha.1 → alpha.2 | Executable bytes, alpha.1 → alpha.2 |
|---|---:|---:|---:|
| Numeric | 1.450922 → 0.396689 (-72.7%) | 93,540 → 88,136 (-5.8%) | 107,072 → 145,200 (+35.6%) |
| JSON | 12.863427 → 9.186604 (-28.6%) | 140,776 → 133,436 (-5.2%) | 668,808 → 701,704 (+4.9%) |
| Float copying | 1.377891 → 0.227626 (-83.5%) | 93,604 → 85,492 (-8.7%) | 112,304 → 151,048 (+34.5%) |

The demonstrated tradeoff is shorter warm builds with larger executables and
slightly lower recorded peak build memory for these three workloads. The fresh
per-command collector uses blocking Linux `wait4`; `ru_maxrss` is KiB with
waited-descendant accounting, not simultaneous summed process-tree RSS. Six
warmups are retained and excluded from the medians. This makes no broad
application-memory, startup, runtime or compiler-bootstrap-memory claim.

## Package contents and integrity

- `alpha2-exact-main-gates/`: complete run/job/check inventories, selected logs,
  verified aggregate ZIPs/JSON, qualification reports and validation scripts.
- `alpha2-exact-main-performance/`: fresh artifact bytes, sample analysis and
  independent acceptance.
- `alpha2-build-memory/`: commands, raw records, outputs, source/toolchain
  bindings, summaries and independent acceptance. Source-home copies, caches
  and built executables are excluded; their recorded hashes are retained.

Each directory's `evidence-files-final.json` is authoritative for this package.
The initial memory `evidence-files.json` is retained history: only the auditor's
script changed while that earlier inventory was being prepared. The final
inventory records that distinction; measurement records did not change.

The separate `alpha2-complete-lean` package holds the full census and proof-delta
qualification. This package contains post-merge workflow/performance evidence,
not a new census or a publication result.

`package_alpha2_main.py` verifies every file declared by the three final
manifests and builds the archive with sorted members, fixed metadata and zero
gzip timestamp. The external manifest records all included bytes, the archive's
SHA-256, Git blob SHA-1 and size. Repack an extracted copy with:

```sh
python3 package_alpha2_main.py --source-root . --readme README.md --output-dir ../repacked
```
