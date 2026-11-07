# Releases

The [Release workflow](../.github/workflows/release.yml) builds native compiler archives
for Linux x86-64/AArch64 and macOS arm64/x86-64, and native Docker images for Linux
amd64/arm64. Linux ARM64 builds use `ubuntu-24.04-arm`, without emulation. PRs run
release unit tests and one Linux archive smoke in the compact distribution job. Full
archive and container matrices run only for release tags/dispatch. Artifacts are retained for 14 days. Published Docker version tags select
the native image through a manifest containing both architectures.

## Prepare publishing

Configure repository Actions secrets through GitHub's settings:

| Secret | Value |
|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub account that can push the image |
| `DOCKERHUB_TOKEN` | Docker access token with repository write permission |

The default image is `DOCKERHUB_USERNAME/pystachy`. Set the repository variable
`DOCKERHUB_IMAGE` to publish under another namespace or organization. Create that
public repository on Docker Hub first. Tokens belong in Actions secrets, never in
source, build arguments, release notes or workflow inputs. `.dockerignore` allows
only build inputs and excludes environment files, keys and caches.

### Publish the hosted compiler to PyPI

PyPI account links do not grant package upload access. Configure a GitHub
[Trusted Publisher](https://docs.pypi.org/trusted-publishers/) for `pystachy`:

| Field | Value |
|---|---|
| PyPI project | `pystachy` |
| Repository owner | `den-run-ai` |
| Repository | `pystachy` |
| Workflow filename | `release.yml` |
| GitHub environment | `pypi` |

For the first upload, add it as a pending publisher in the PyPI account's
Publishing settings. Configure the matching `pypi` GitHub environment and its
deployment restrictions before publishing. No long-lived PyPI token is needed.

Run **Release** manually with an already published tag such as `v0.2.0` and set
`pypi` to `verify` to build and check the distributions, or `publish` to upload
them after those same checks. Leave `pypi` set to `off` for the native release
process below. The publishing workflow revision supplies the upload tooling;
package sources always come from the requested release tag.

Choose a workflow ref already permitted by the `pypi` environment. An approved
release branch can publish a newer tag when its `release.yml`, `pypi_release.py`
and `release_gate.py` match the reviewed publishing revision. The workflow ref
supplies publishing logic; the `version` input selects package sources. Keep
deployment restrictions unchanged.

The PyPI path requires the tag, `VERSION`, published release commit and successful
main CI to agree. It builds a source distribution and its wheel, validates their
metadata, and exercises clean pip/uv installs in JIT and AOT. Only the separate
upload job receives OIDC permission; it uploads those tested artifacts with
attestations. Native archives and Docker publication do not run in this mode.
The workflow retains the source SHA and distribution checksums with its artifact.
Changed package contents require a new version; existing PyPI files are not replaced.

## Publish a version

1. Set [VERSION](../VERSION) to the intended semantic version and add its curated notes
   as `docs/releases/VERSION.md`, such as [v0.1.0-alpha.4](releases/v0.1.0-alpha.4.md).
   Then merge the version bump, intended fixes and packaging changes into `main`.
2. Wait for **CI**, **Installation**, **Lint** and **Packages** to succeed on the exact
   `main` commit. CI on a `main` push includes the complete Linux x86-64 and Linux ARM64
   verification matrices; a success on only one architecture does not satisfy this gate.
   The sampled PR profile is not release evidence.
3. Run **Release** manually from `main`, with a new tag matching `VERSION`.
   Alternatively, push that tag pointing to a verified commit on `main`.
4. Download an archive and `SHA256SUMS` from the release, check the archive's hash, and
   confirm that its `bin/pystachy --version` and `docker run --rm IMAGE:VERSION --version`
   report the new version and the release commit.

The workflow verifies that the source commit belongs to `main` and waits up to ten
minutes for all four verification workflows on that commit. A failure or cancellation
blocks publication. A published version cannot be replaced, and an existing tag must
resolve to the selected commit. Create a new version for changed code.

The release notes are the version's file under `docs/releases/`, followed by the
generated asset list, Docker image, installation link and source commit. Every Release
run and PR distribution check fails if `VERSION` has no notes file. GitHub shows the
notes outside the repository, so they use absolute links and no top-level title; the
release is titled "Pystachy VERSION". A retried publication keeps an existing draft's notes.

Keep the current version's notes in the source tree: they are a required packaging input.
Older published notes are available on [GitHub Releases](https://github.com/den-run-ai/pystachy/releases)
and at their release tags. When retiring a report cited by release notes, pin the evidence
link to the commit that contains it; a future release tag cannot resolve a deleted file.

The same version identifies the Git tag, GitHub release, binary archive names, manifest,
Docker version tag and OCI labels. `pystachy --version` (or `-V`) reports the release
version and exact source commit from adjacent metadata, without starting LLVM or Python.
Ordinary source builds report the declared version; a commit may be `unknown` before
installation. Increment the patch version for fixes, the minor version for new features,
and the major version for incompatible changes. Use a prerelease suffix for alpha,
beta and release-candidate builds. A plain pre-1.0 version publishes as a normal release.

Every platform rebuilds the compiler to its bootstrap fixed point. Archives include a
relative launcher, runtime sources, libraries, licenses, source metadata and checksums.
Smoke tests extract and move the archive, then compare JIT/AOT output with CPython using
a compiler PATH without Python and a cache outside the installation. GC stress is tested
as well, the programs include a JSON round trip and code-point string indexing, and a warm
JIT run must reuse the cached runtime, which on Linux includes its shared library. The
Linux payload audit records ELF architecture, shared-library dependencies and required
symbol versions, rejecting binaries above the declared glibc 2.39 baseline. Its reports
accompany the Linux archive artifacts; they do not establish manylinux compatibility or
a baseline for executables users later generate.

Each native Docker job downloads its architecture's tested archive, verifies its hashes,
manifest, version, commit and target, and supplies its installed payload as the named
`build` context in the Docker build. This replaces the source-bootstrap stage; the image
contains the same compiler and resources that passed the archive checks. Ordinary local
`docker build` still bootstraps from source. The final image verifies JIT/AOT without
Python; CI checks its architecture, an unprivileged user and bind-mounted inputs/outputs
on the matching native runner.

Only after every build and smoke passes does the publishing job receive write permission.
It checks artifact hashes, loads both tested images, pushes architecture-specific tags
(`VERSION-amd64` and `VERSION-arm64`), and combines their immutable digests into the
`VERSION` manifest. The four archives, their checksum files, Linux ABI reports and
`SHA256SUMS` are uploaded to a GitHub release. A version
containing `-` is a prerelease and never advances Docker's `latest` tag. Newer stable
versions advance both `latest` pointers after the GitHub release is published; publishing
an older stable version cannot move them backwards. Publication jobs are serialized.

If publication fails before the draft GitHub release becomes public, a retry may complete
the draft only for its original source commit. An existing Docker version tag is accepted
only if both native image configurations match the tested images and the manifest contains
exactly the supported architectures. Existing per-architecture tags from a partial attempt
must match too; otherwise choose a new version. If the
GitHub release is already public, use a new version for changed assets.

If a transient failure interrupts the final stable `latest` promotion, recover it without
rebuilding or uploading assets. Install Docker Buildx, authenticate `gh` and `docker`, set `GH_TOKEN` in your
environment, then run:

```sh
python3 tools/release_promote.py --repository den-run-ai/pystachy \
  --version v0.1.0 --image DOCKERHUB_NAMESPACE/pystachy
```

The same helper runs in the workflow. It requires a published stable release, resolves its
tag commit, and verifies the revision and version labels on every image before copying the
entire registry index by digest to `latest`. A local pull/tag/push would retain only the host
architecture. The helper verifies the copied digest before advancing GitHub's `latest`.
It can repair Docker when GitHub already points to this version,
and it refuses to displace a newer version. Run recovery after other release publication
jobs finish, so manual promotion does not race an active release.

## Local packaging checks

```sh
make
python3 -m unittest discover -s tools -p 'test_release*.py'
python3 tools/release.py --version v0.1.0-alpha.3 --output-dir dist
python3 tools/release_smoke.py dist/pystachy-v0.1.0-alpha.3-linux-x86_64.tar.gz
docker build -t pystachy:test .
docker run --rm --user 10001:10001 --entrypoint pystachy-smoke pystachy:test
```

Use `linux-aarch64` on Linux ARM64 or the matching macOS archive target on macOS. Builds use the pinned Python version and
the platform's LLVM version. Archive metadata is normalized for reproducibility;
`SOURCE_DATE_EPOCH` or `--epoch` can override the source commit timestamp.

### Inspect Linux payloads

[`tools/linux_abi.py`](../tools/linux_abi.py) inspects every ELF executable and shared
library in an extracted release directory without running the payload. It records
hashes, architectures, interpreters, direct dependencies, required symbol versions
and library search paths. Install GNU `readelf` from binutils before running it:

```sh
python3 tools/linux_abi.py EXTRACTED_RELEASE \
  --architecture x86_64 --max-glibc 2.39 --json build/linux-abi.json
python3 -m unittest discover -s tools -p 'test_linux_abi.py'
```

Select `aarch64` for the Linux ARM64 artifact. The supplied root and entries beneath
it must not be symlinks; aliases in the root's parent path are resolved normally.
Malformed or unreadable ELF evidence fails inspection. Exit status is 0 when the
requested architecture and symbol constraints pass, 1 for recorded violations,
and 2 for invalid input or failed inspection.

The report does not resolve external dependency trees or `dlopen` dependencies,
check CPU instructions or kernel support, or certify manylinux compatibility.
Generated AOT programs and external LLVM tools need their own audits and execution
tests. Before lowering the release baseline, validate the complete payload and the
advertised JIT/AOT, GC and FFI behavior on the oldest supported environment; see the
[30 October 2026 assessment](https://github.com/den-run-ai/pystachy/blob/a2cb8a3638d715577a7ab1cd1e4a0d6b01b6cdf2/docs/reports/linux-portability.md)
and the remaining portability work in
[#998](https://github.com/den-run-ai/pystachy/issues/998).
