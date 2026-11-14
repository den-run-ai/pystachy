# Alpha.2 publication and public artifact verification

Pystachy **v0.5.0-alpha.2** uses source commit
`80490143498d149d407343ba1cb7aedb1db2d2c5`, tree
`717a8c9386ae9f5f6545cc3686a9e22282fc560c`. The complete tree equals the qualified
PR #1488 head `950c0440ad793dc6c34664f591383a5e6bba14dd`.

The release is published and its public artifacts are verified.

| Channel | Published result |
|---|---|
| GitHub | [v0.5.0-alpha.2 prerelease](https://github.com/den-run-ai/pystachy/releases/tag/v0.5.0-alpha.2); all 11 assets downloaded and verified |
| Docker | `dta67/pystachy:v0.5.0-alpha.2`, native Linux amd64 and arm64 |
| PyPI | [0.5.0a2](https://pypi.org/project/pystachy/0.5.0a2/), public wheel and source distribution |

## Qualification

All seven exact-main workflows passed: CI, Installation, Lint, Packages, Performance
smoke, Coverage and Variants. Across these runs there were 131 successful jobs and one
expected skip; the longest job took 670 seconds. Both CI architecture aggregates
accepted 58/58 checks across 35 groups and 192/192 runtime-cache checks. The 19-row PR
budget and 15-minute per-job cap remain in force; full main qualification has a larger
matrix.

The fresh full Lean census covered 2,550 programs. All 2,529 shared programs remained;
21 new programs contributed 1,195 proved obligations and eight shared null checks each
added one, totaling 1,203 additional proofs. There were no missing cases, newly unproved
results or proof-coverage losses. Strict storage passed 18,582/18,582 obligations across
175 selected programs. Existing bounded-model gaps in other categories remain disclosed;
this is not a proof of the entire compiler.

The 4,579-case IR comparison had no newly rejected programs; all substantive IR and
diagnostic changes were explained. Bootstrap fixed points and targeted JIT/AOT, GC,
cache and compatibility checks passed. Two independent current-tree source reviews
completed without actionable findings. Four GitHub Codex service refresh attempts and
the local CLI attempts failed before completing a review; none is counted as a passed
review. The sole historical bot finding was reproduced against actual test discovery
and CI evidence, found inapplicable and resolved.

- [Full Lean and review evidence](https://github.com/den-run-ai/pystachy/tree/f05236f58a51013c49aba6b06963e18edf8f2847/research/v0.5.0-alpha-qualification/post-storage/alpha2-full)
- [Exact-main gates, performance and memory evidence](https://github.com/den-run-ai/pystachy/tree/7e37d27bbda6d257e1b2984d679eba885e2db7ca/research/v0.5.0-alpha-qualification/post-storage/alpha2-main)
- [Review disposition](https://github.com/den-run-ai/pystachy/pull/1488#issuecomment-6880303611)

## Compilation cost and performance

The fresh exact-main Performance artifact compared alpha.1 source `a73c56c9` with
alpha.2 source `80490143`: 11 workloads, 49 comparisons classified `ok`, no warnings
or unconfirmed changes. Warm AOT builds were 23.5–82.3% shorter in that run. Runtime
changes were mixed and do not support a general runtime-speed claim. A single bootstrap
pair measured 155.481 to 162.397 seconds (+4.4%); one pair is not a confirmed trend.

A separate serial comparison used three alternating measured warm builds per workload
and release, six warmups, private caches, disabled program caching and CPython output
oracles. All 24 builds produced the expected outputs.

| Workload | Median warm build seconds, alpha.1 → alpha.2 | Compiler peak RSS KiB | Executable bytes |
|---|---:|---:|---:|
| Numeric | 1.450922 → 0.396689 (−72.7%) | 93,540 → 88,136 (−5.8%) | 107,072 → 145,200 (+35.6%) |
| JSON | 12.863427 → 9.186604 (−28.6%) | 140,776 → 133,436 (−5.2%) | 668,808 → 701,704 (+4.9%) |
| Float copy | 1.377891 → 0.227626 (−83.5%) | 93,604 → 85,492 (−8.7%) | 112,304 → 151,048 (+34.5%) |

RSS is per-command `wait4` peak usage with waited-descendant accounting, not the sum
of simultaneously resident processes or application memory. These small-workload,
warm-cache measurements do not establish universal performance gains. The publication
notes retain their earlier, separately identified measurements; this newer evidence
adds exact-main and memory qualification without rewriting that history.

## Native and Docker publication

[Native Release #67](https://github.com/den-run-ai/pystachy/actions/runs/43626857296)
completed eight jobs successfully, with two expected PyPI skips; its longest job took
683 seconds. All four platform payloads and both native Docker architectures passed
their execution and packaging gates before publication.

All 11 [public GitHub assets](https://github.com/den-run-ai/pystachy/releases/tag/v0.5.0-alpha.2)
were downloaded and matched the tested bytes. The downloaded Linux x86-64 launcher
reported the full release source commit. Docker image `dta67/pystachy:v0.5.0-alpha.2`
has public index digest
`sha256:ec762302831e863f92ab31ec061131088e46ede67000ea592ecd12a846449104`.
Both public configurations equal the tested native images. All 11 distinct public
blobs and 14 ordered layer references were downloaded: 407,152,903 compressed bytes,
with every compressed digest/size, decompressed diff ID and unpacked size verified.

## PyPI and stable pointers

[PyPI Release #68](https://github.com/den-run-ai/pystachy/actions/runs/43630294045)
completed two jobs successfully, with four expected native skips; its longest job
took 76 seconds. The approved publisher revision was
`6e5544cfa3eecb8329e4f4cb19d2e0ac3e99b1bf`; package sources came from the published
alpha.2 tag at `80490143498d149d407343ba1cb7aedb1db2d2c5`. Clean pip and uv JIT/AOT,
external-cache and uninstall checks passed before the tested distributions were uploaded.

The actual public wheel and source distribution match the tested workflow files byte
for byte. Independent source comparison verifies all 163 wheel source files, three
license files and 168 sdist source files against exact release Git blobs, including the
complete wheel RECORD. Fresh isolated local pip and uv installations each checked all 163 installed
payload files against the public wheel, installation metadata and the console version.
Assertions were enabled in the verifier and both installed probes; the actual execution
context is recorded. Local supplemental checks cover installation and version; runtime
execution is supplied by the publishing workflow's checks against these same bytes.

The hosted CLI reports `pystachy v0.5.0-alpha.2 (commit unknown)` because package data
includes VERSION but omits REVISION. Exact source identity is established separately
by SOURCE.json, the workflow gates and immutable Git source-byte comparisons.

The final public comparison confirms GitHub latest remains v0.4.0 at
`5f81cc2563d231501952104e991d858e670325ac`, PyPI's default remains 0.4.0 and Docker latest
remains `sha256:037f5691b17c9ae9a8afb6be79bf6870a1a81fb9ada67ec5e3d9dd5b08d60d01`.

An initial preflight overstrictly compared the entire historical publisher workflow
with main. The independently reviewed resolution established that both PyPI jobs,
their workflow header and both gate helpers are byte-identical; the two differences
are historical native-note steps outside the PyPI path. The publisher workflow checks
out and builds package metadata from the release tag. The diagnostic and exact diff
are retained. No publisher branch, source or permission change was made.

## Release bookkeeping and evidence archive

The [180-PR disposition snapshot](https://github.com/den-run-ai/pystachy/tree/3790f5ac4ca4ee660bf747bfc062b22b53d5d897/research/v0.5.0-alpha-qualification/dispositions)
assigns 21 included, 65 conditional and 94 deferred rows. This is a scoped inventory,
not a claim that all remaining PRs received code review. The final bookkeeping addendum
records any subsequent closures and the actual published status without rewriting the
original snapshot. After final acceptance, #1415, #1281 and #1282 were closed with
fresh live-head, whole-head ancestry and closed-state readback evidence; all their
commits are already included through #1488. Alpha.3–5, release candidates and stable
remain future work.

The final independent acceptance receipt is `acceptance.json`, SHA-256
`7ac9e86a7d4d48482d7d2a55ae77015d04daf21381529008ea6eb50e9ebbbec3`;
the readable audit is `acceptance.md`. Both are also retained at their original
`release-alpha2-verification/independent-audits/alpha2-final.*` paths in the archive.

The archive preserves raw workflow logs, dispatch/source records, public manifests,
checksum receipts, independent audits, verification helpers and the stable baseline.
Its manifest records every included file by SHA-256. Large public binaries, images
and distributions are represented by verified hashes and published locations.
No scheduled monitoring was used. This evidence belongs on the research branch and
must not be merged into main.
