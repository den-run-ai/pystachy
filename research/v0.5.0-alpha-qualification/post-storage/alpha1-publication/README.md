# Alpha.1 publication and public artifact verification

Pystachy **v0.5.0-alpha.1** is published and verified from commit
`a73c56c92f3aad4b490307a5d1b882e487a57f55`, tree
`3c9a009434d68906889651d148cb29f6022d2f1f`.

| Channel | Published result |
|---|---|
| GitHub | [v0.5.0-alpha.1 prerelease](https://github.com/den-run-ai/pystachy/releases/tag/v0.5.0-alpha.1); all 11 assets downloaded and verified |
| Docker | `dta67/pystachy:v0.5.0-alpha.1`, native Linux amd64 and arm64 |
| PyPI | [0.5.0a1](https://pypi.org/project/pystachy/0.5.0a1/), public wheel and source distribution |

## Qualification and publication

CI, Installation, Lint and Packages passed on the exact release commit. The complete
main CI run passed 73 jobs with one expected skip; each architecture's aggregate
accepted 58 checks across 35 groups. Performance smoke also passed: the fresh artifact
contains 11 workloads and 49 comparisons classified `ok` against the pre-repair main.
Historical comparisons with v0.4.0 remain separately identified.

The full Lean census accepted 2,529 unique programs and all 175 selected storage
programs, with 18,582/18,582 storage obligations proved. Its source commit has the same
complete tree as the release commit. Compared with the pre-repair census, only the
context-manager storage dictionary changes: 7/7 becomes 19/19 and both unsupported
functions disappear. Existing bounded-model gaps in other categories remain disclosed;
this is not a proof of the entire compiler.

[Complete proof evidence](https://github.com/den-run-ai/pystachy/tree/37aeeed88c85b26bc0cdda5d52d1d835980f7aac/research/v0.5.0-alpha-qualification/post-storage/alpha1-full)
and [gate/review evidence](https://github.com/den-run-ai/pystachy/tree/37aeeed88c85b26bc0cdda5d52d1d835980f7aac/research/v0.5.0-alpha-qualification/post-storage)
are preserved separately.

[Native Release 43618595752](https://github.com/den-run-ai/pystachy/actions/runs/43618595752)
completed eight jobs successfully with two expected PyPI skips. The longest job took
730 seconds. All four native platforms completed bootstrap fixed points, Python-free
relocation, JIT/AOT, GC and cache checks. Both Linux payloads passed their declared
glibc 2.39 ABI bound. Both Docker images passed native architecture, unprivileged-user
and bind-mount JIT/AOT checks.

[PyPI Release 43621120891](https://github.com/den-run-ai/pystachy/actions/runs/43621120891)
completed two jobs successfully with four expected native skips. Its longest job took
110 seconds. The approved publisher revision was
`6e5544cfa3eecb8329e4f4cb19d2e0ac3e99b1bf`; package sources came from the published
alpha.1 tag at `a73c56c92f3aad4b490307a5d1b882e487a57f55`. Clean pip and uv JIT/AOT,
cache and uninstall checks passed before the tested distributions were uploaded.

## Verification of the public bytes

All GitHub assets match the tested release artifacts. Docker's public index is
`sha256:1ae046bdbb9a72202a9daa44b756673cf1436166db2345f8ed2ab69fa2a954f2`.
Both public manifests/configurations match the tested native images; all 11 distinct
public blobs and 14 ordered layer references were downloaded and checked by compressed
digest/size and decompressed diff ID (407,072,225 compressed bytes).

The public PyPI wheel and source distribution are byte-identical to the tested files.
An independent audit matched every packaged source file to immutable release Git
blobs and verified the wheel RECORD. Supplemental local fresh pip/uv installations
each checked all 162 installed payload files against the public wheel, isolated
installation metadata and the console version.

The hosted CLI reports the correct version with `commit unknown` because its package
data omits REVISION. Exact source identity is established by SOURCE.json, workflow
gates and byte comparisons. The first supplemental probe incorrectly required the
native console format; its failed receipt and diagnostic are retained alongside the
successful corrected check and execution-context record.

GitHub latest and PyPI's default version remain v0.4.0/0.4.0. Docker latest remains
`sha256:037f5691b17c9ae9a8afb6be79bf6870a1a81fb9ada67ec5e3d9dd5b08d60d01`.

## Evidence archive

The archive contains raw workflow logs, dispatch/source records, public manifests,
checksum receipts, independent audits, verification helpers and the unchanged stable
baseline. Its manifest records every included file by SHA-256. Large public binaries,
images and wheels are represented by verified hashes and their published locations.
No scheduled monitoring was used. This is release evidence on a research branch;
it must not be merged into main.
