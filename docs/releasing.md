# Releases

The [Release workflow](../.github/workflows/release.yml) builds native compiler archives
for Linux x86-64/AArch64 and macOS arm64/x86-64, and native Docker images for Linux
amd64/arm64. Linux ARM64 builds use `ubuntu-24.04-arm`, without emulation. Pull requests
changing packaging run the same builds and smoke tests without publishing or Docker
credentials. Artifacts are retained for 14 days. Published Docker version tags select
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

## Publish a version

1. Set [VERSION](../VERSION) to the intended semantic version and add its curated notes
   as `docs/releases/VERSION.md`, such as [v0.1.0-alpha.3](releases/v0.1.0-alpha.3.md).
   Then merge the version bump, intended fixes and packaging changes into `main`.
2. Wait for **CI**, **Installation**, **Lint** and **Packages** to succeed on the exact
   `main` commit. CI includes the complete Linux x86-64 and Linux ARM64 verification
   matrices; a success on only one architecture does not satisfy this gate.
3. Run **Release** manually from `main`, with a new tag matching `VERSION`.
   Alternatively, push that tag pointing to a verified commit on `main`.
4. Download an archive and `SHA256SUMS` from the release, check the archive's hash, and
   confirm that its `bin/pystachy --version` and `docker run --rm IMAGE:VERSION --version`
   report the new version and the release commit.

The workflow verifies that the source commit belongs to `main` and waits up to 20
minutes for all four verification workflows on that commit. A failure or cancellation
blocks publication. A published version cannot be replaced, and an existing tag must
resolve to the selected commit. Create a new version for changed code.

The release notes are the version's file under `docs/releases/`, followed by the
generated asset list, Docker image, installation link and source commit. Every Release
run, including a pull request's, fails if `VERSION` has no notes file. GitHub shows the
notes outside the repository, so they use absolute links and no top-level title; the
release is titled "Pystachy VERSION". A retried publication keeps an existing draft's notes.

The same version identifies the Git tag, GitHub release, binary archive names, manifest,
Docker version tag and OCI labels. `pystachy --version` (or `-V`) reports the release
version and exact source commit from adjacent metadata, without starting LLVM or Python.
Ordinary source builds report the declared version; a commit may be `unknown` before
installation. Increment the patch version for fixes, the minor version for new features,
and the major version for incompatible changes. Use a prerelease suffix while the
compiler is experimental.

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
