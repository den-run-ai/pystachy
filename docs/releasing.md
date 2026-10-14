# Releases

The [Release workflow](../.github/workflows/release.yml) builds native compiler archives
for Linux x86-64 and macOS arm64/x86-64, and a Docker image for Linux amd64. Pull requests
changing packaging run the same builds and smoke tests without publishing or Docker
credentials. Artifacts are retained for 14 days.

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

1. Merge the intended fixes and packaging changes into `main`.
2. Wait for **CI**, **Installation** and **Lint** to succeed on the exact `main` commit.
3. Run **Release** manually from `main`, with a new tag such as `v0.1.0-alpha.1`.
   Alternatively, push that tag pointing to a verified commit on `main`.

The workflow verifies that the source commit belongs to `main` and waits up to 20
minutes for all three verification workflows on that commit. A failure or cancellation
blocks publication. A published version cannot be replaced, and an existing tag must
resolve to the selected commit. Create a new version for changed code.

Every platform rebuilds the compiler to its bootstrap fixed point. Archives include a
relative launcher, runtime sources, libraries, licenses, source metadata and checksums.
Smoke tests extract and move the archive, then compare JIT/AOT output with CPython using
a compiler PATH without Python and a cache outside the installation. GC stress is tested
as well. The Docker build also verifies JIT/AOT without Python; CI checks an unprivileged
user and bind-mounted inputs/outputs.

Only after every build and smoke passes does the publishing job receive write permission.
It checks artifact hashes, loads the tested image, pushes its version tag, and uploads the
three archives, their checksum files and `SHA256SUMS` to a GitHub release. A version
containing `-` is a prerelease and never advances Docker's `latest` tag. Newer stable
versions advance both `latest` pointers after the GitHub release is published; publishing
an older stable version cannot move them backwards. Publication jobs are serialized.

If publication fails before the draft GitHub release becomes public, a retry may complete
the draft. An existing Docker version tag is accepted only if its image matches the tested
image exactly; otherwise choose a new version. If the GitHub release is already public,
use a new version rather than overwrite its assets.

## Local packaging checks

```sh
make
python3 -m unittest discover -s tools -p 'test_release*.py'
python3 tools/release.py --version v0.1.0-alpha.1 --output-dir dist
python3 tools/release_smoke.py dist/pystachy-v0.1.0-alpha.1-linux-x86_64.tar.gz
docker build -t pystachy:test .
docker run --rm --user 10001:10001 --entrypoint pystachy-smoke pystachy:test
```

Use the matching macOS archive target on macOS. Builds use the pinned Python version and
the platform's LLVM version. Archive metadata is normalized for reproducibility;
`SOURCE_DATE_EPOCH` or `--epoch` can override the source commit timestamp.
