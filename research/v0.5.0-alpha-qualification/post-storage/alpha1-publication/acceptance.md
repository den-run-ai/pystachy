# Alpha.1 final independent release acceptance

**Passed. Alpha.1 is published on GitHub, Docker Hub and PyPI, and the public artifacts match the qualified release source and successfully tested payloads.**

Release: v0.5.0-alpha.1 (PyPI 0.5.0a1). Exact source commit: a73c56c92f3aad4b490307a5d1b882e487a57f55. Source tree: 3c9a009434d68906889651d148cb29f6022d2f1f.

| Evidence area | Accepted result |
|---|---|
| Exact-main gates | CI, Installation, Lint and Packages succeeded for the exact source at native preparation and publication; PyPI independently rechecked the published tag and exact-main gates. |
| Four native platforms | Linux x86-64/AArch64 and macOS arm64/x86-64 completed bootstrap fixed points, Python-free relocation, JIT/AOT/GC and warm runtime-cache checks. Linux default program-cache and complete payload ABI checks passed. |
| GitHub publication | Non-draft prerelease at the exact commit; all 11 public assets were downloaded and verified against tested archives/checksums/ABI reports. |
| Docker publication | Both native linux/amd64 and linux/arm64 images passed UID 10001 JIT/AOT and bind-mount execution. Public configurations equal tested images. All 11 unique public blobs and 14 ordered layer references passed compressed digest/size and decompressed diff-id verification. |
| PyPI publication | Clean pip and uv JIT/AOT/cache and uninstall checks passed. Both uploads returned HTTP 200. The public wheel and sdist equal tested bytes; every packaged source file matches the release Git commit. |
| Complete Lean census | 2,529 programs; all 175 strict-storage programs accepted with 18,582/18,582 obligations proved. No new failed/unproved outcomes or unexplained proof-coverage loss. The sole pre-repair change improves context-manager storage from 7/7 to 19/19 and removes both unsupported functions. |
| Stable pointers | GitHub latest and PyPI default remain 0.4.0; Docker latest retains the pre-alpha digest. |

Native Release run 43618595752 finished with eight successful jobs and two expected PyPI skips; the longest job took 12m 10s. PyPI run 43621120891 finished with two successful jobs and four expected native skips; its longest job took 1m 50s. Both stay within the 15-minute job cap.

Published GitHub release: https://github.com/den-run-ai/pystachy/releases/tag/v0.5.0-alpha.1

Published PyPI package: https://pypi.org/project/pystachy/0.5.0a1/

Public Docker index: dta67/pystachy:v0.5.0-alpha.1 at sha256:1ae046bdbb9a72202a9daa44b756673cf1436166db2345f8ed2ab69fa2a954f2.

The hosted wheel reports “commit unknown” because its released package data omits REVISION. That matches the driver and existing hosted smoke contract. The retained supplemental probe's first native-format assertion failure is explained; exact package source identity is independently established by provenance and byte comparisons. It does not negate the publishing workflow's completed pip/uv JIT/AOT checks.

This aggregate binds the separately frozen native/Docker, PyPI and full Lean independent audits by hash. The companion JSON preserves those receipt paths and exact identities. No network, new downloads, installations, payload executions, compilation or Lean reruns were performed for the aggregation. This is independent agent evidence review, not a successful GitHub/CLI Codex review.

## Supplemental public-wheel installations

The corrected additional local check also passed for **two fresh isolated installations**, one with pip and one with uv. Each installation reports metadata version 0.5.0a1, the expected hosted console version with commit unknown, and **all 162 installed payload files byte-identical to the verified public wheel**. Both install and version commands returned zero. The earlier failed native-format probe and its diagnostic remain preserved.

The exact helper and public retrieval receipt hashes are bound to a separate independent supplemental receipt. Its assertions ran under the retained ordinary pinned Python invocation; the executor's confirmation explicitly states that optimize=0 and the absent PYTHONOPTIMIZE were observed afterward in the same unchanged environment. The complete publishing workflow already supplies independent clean pip/uv JIT/AOT evidence. No JIT/AOT execution is claimed for these additional local install/version checks.

This additive final receipt supersedes alpha1-final.json solely to include the completed supplemental installations; it preserves the original passed release and Lean evidence.
