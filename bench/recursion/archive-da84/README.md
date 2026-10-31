# Archived da84d382 evidence

This directory publishes completed evidence from the archived PR #996 session. It evaluates source `da84d382ff83f09e46d4ef104e62e6f64e9c37c1`, tree `903a72dce156018f83f69f1e8b4d74a6f14e99dd`, against main `06e3ad5d08514ba31fb231fe4636a962fe6578e3`. It does not validate later PR commits.

| File | Scope |
|---|---|
| [backend-attribution/curated.json](backend-attribution/curated.json) | Whole-tool instruction counts, selected LLVM attribution, exact source/tool/input identities, and limitations |
| [backend-attribution/backend-attribution-da84-full.json.gz](backend-attribution/backend-attribution-da84-full.json.gz) | Lossless compressed complete backend record; decompresses to the original 7,754,882-byte report |
| [validation/validation-final-da84.json.gz](validation/validation-final-da84.json.gz) | Complete 3,918-case compilation status/diagnostic export, 150 fixture executions, source inventories, bootstrap and CI bindings |
| [validation/validation-final-da84-manifest.json](validation/validation-final-da84-manifest.json) | Original validation export hashes and compression identity |
| [reproduction/README.md](reproduction/README.md) | Original ordered reproduction instructions and dependencies |
| [publication-manifest.json](publication-manifest.json) | Exact original-to-published file mapping, byte counts, SHA256 hashes, and known archival gap |

The 21 copied files retain their original bytes. The compressed reports were checked against the complete retained JSON records before publication. The reproduction scripts retain original workspace assumptions: read their README before running them. This selection is not a standalone replay package. Source checkouts, native compilers, the LLVM/Python installations, caches, and the full raw LLVM corpus remain in the user-provided archival ZIPs.

No compiler or benchmark execution was performed to publish this directory. The source checkpoint's correctness verification completed, while performance acceptance remained open. Whole `lli` counts include JIT compilation, executed program, runtime/GC, and teardown; they are not pure startup measurements. Inclusive profile rows overlap and must not be summed.

The older `recursion-region-startup-diagnostics.json` was lost before archival. Its recorded identity is 85,660 bytes, SHA256 `8d4ccaa64ec19cd39484db48e28eae7a4d7ca91edbf8cc5b6955bae267c00503`. This publication does not recover or reconstruct it. Previously published partial transcript vectors remain explicitly partial.
