# Release blocker evidence — 29 October 2026 UTC

Raw reproduction evidence; this research branch must not be merged into main.

## Evaluated sources

- Identity PR #981: `ac28b3cf4880cb69774e7900d4681c44261aa21f`, tree `bbdae6c42634bf5dc82f47be5dad24197c2b7d53`; merged as `9b50a3851ed66c792c07f4c7cbaabd6af04b6d8e` after all applicable workflows passed.
- Runtime PR #980: `d58a791581fedce4d6d8ca66924c9e639e8392a3`, tree `6f9ebf7b7b7e6fd47f44a33043b7ff8e8140904e`.
- Combined PR #973: `9fd73f34a36cfae6196f165628b2ed19fa16538b`, tree `c996c5698c3b201d959cde9e3fc9fff3313cc549`.
- Runtime and combined final CI were still pending at this evidence checkpoint. Their production inputs match the measured sources; the final 11-file update contains only fixtures, provenance and shrinking exception manifests.

## Archives

| File | SHA256 | Contents |
|---|---|---|
| runtime-final.tar.gz | `1a0832e5eb656e85b5da59037fa78205fc6d603a01d08e41b802f5f864310ba2` | Exact harness/input bytes, source/build hashes, all JSON and Counter timing pairs, profile totals/function summaries, reconstructed 32-key control, rejected scalar-lookup trial, commands/output checks, and source-equivalence manifest. |
| verification-final.tar.gz | `0e10ef8c7beb4f08b6a9bd742794c10986e2feb027b9e107005943a4582c655a` | Complete final oracle metadata/results and changed-case diffs, explicit promoted-GC reports/logs, scripts, source/binary provenance, selected focused logs and checksums. |
| isolated-runtime.tar.gz | `e76d1b756f74644567fee9a8d03d1fef5eeaf52f037640fb18cd4ef633c4a665` | Earlier isolated runtime measurements, retained separately. |

The archives are text-only payloads. Reproducible caches, binaries, thousands of raw LLVM files and full Callgrind files are omitted; source, compiler, executable, IR and profile hashes remain recorded. The verification README identifies earlier misleading promoted “GC” filenames: the opt-in harness cleared the stress flag, so those runs count as normal runs. Final direct overlays explicitly set GC after sanitation and pass 34/34 checks for both identity and scoped compilers.

Final native comparisons: identity 3,861 cases / 3,851 identical / seven explained IR changes / three intended new acceptances; scope 3,865 cases / 3,861 identical / four intended IR changes / identical statuses and diagnostics. Neither introduces a new rejection.

The accepted runtime patch removes 54.189M JSON instructions, 51.5% of the excess over alpha.3, leaving 3.92%. Paired time overhead versus alpha.3 remains 3.12% AOT / 5.68% warm JIT with overlapping shared-host ranges. Counter regains alpha.3's layout and measured range. The reconstructed numeric 32-key control is not the unavailable historical 124M input and retains 7.94% instruction overhead. The scalar-lookup trial was rejected for adding 10.27M instructions; it is not in the accepted source.
