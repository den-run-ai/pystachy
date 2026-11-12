# Pystachy v0.4.0-alpha.6 publication audit

**Passed.** The native archives, both Docker architectures, and the public PyPI wheel/source distribution match the outputs retained by the successful publication workflows. Public-wheel installations through both pip and uv passed the compiler smoke checks.

Observed at 2026-11-12T21:12:55Z. Release source: `0b13a2121014d8256954c6af50339ff0de8dac62`. Git tree: `681565b5368bf103bc00e39932ee061a8adf08aa`. Package version: `0.4.0a6`.

[GitHub prerelease 443508043](https://github.com/den-run-ai/pystachy/releases/tag/v0.4.0-alpha.6) was published at 2026-11-12T21:04:54Z; its tag resolves to the source commit above. [Native/Docker run 43303651615](https://github.com/den-run-ai/pystachy/actions/runs/43303651615) and [PyPI run 43306789202](https://github.com/den-run-ai/pystachy/actions/runs/43306789202) both completed successfully.

## Native artifacts

All four public archives, four individual checksum files, and two Linux ABI reports are byte-identical to the tested build artifacts. The publication job generated the eleventh asset, `SHA256SUMS`; all four entries match the archive hashes below.

| Target | Public archive SHA-256 | Verified manifest files |
| --- | --- | ---: |
| linux-x86_64 | `50180c07169466b6230768e572ef6dbec1ca5aec040a18facceeba7222c349f1` | 117 |
| linux-aarch64 | `b002ef59b7c33b52e7b608fdb161360ca4ea0f45317b460592fe8827fb65f204` | 117 |
| macos-arm64 | `63d5ed66def30ee47a6ad349c8aa85b6c80a306d21c7aa921299e7b44a1096ab` | 117 |
| macos-x86_64 | `a209d0f8cf0b89b31d13048ef3bb49dd6e58524ee801471cb39e2069a29658d4` | 117 |

Each archive has the expected platform executable header, manifest identity, version and source revision. Every manifest file digest was verified. The downloaded Linux x86_64 executable also reported the exact release version and full source commit with LLVM unavailable.

The four hosted native jobs passed the compiler and runtime three-stage fixed points, packaging and relocation, normal and GC-stressed JIT/AOT, and warm-cache checks. Both Linux jobs also verified default program-cache population and a subsequent cache hit. See the run/job IDs and manifest hashes in `audit.json`.

## Docker images

Image: `dta67/pystachy:v0.4.0-alpha.6`. Public multiarchitecture index: `sha256:4552810e9cb9cdd52cb4a904d173ec7455965921f6de8232fa422c81e173cbfa`.

| Architecture | Public config digest, identical to tested config | Public compressed layer bytes verified |
| --- | --- | ---: |
| linux/amd64 | `sha256:4e0b5f29bc60b1c5eadb31f176bbe1a581978112b8d4f0fdb4c454abea7df3a4` | 205,275,326 |
| linux/arm64 | `sha256:34505bf2f60e70c04e8eec603c564712959a98d26569a45be88e7205f27b57d2` | 201,653,337 |

Both configs carry the exact release version and source revision. All seven compressed layers per architecture were downloaded and hashed; their uncompressed diff IDs match the tested saved images. `audit.json` records every manifest, config, compressed-layer and diff-ID digest, the saved-image archive hashes, and the corresponding workflow artifact IDs.

Both hosted architecture jobs passed installed-image and unprivileged bind-mount JIT/AOT smoke checks. There was no local Docker daemon; the public readback used complete config/layer identity verification against those tested images.

## PyPI distributions and installation

The approved workflow ran from `release/pypi-v0.2.0` at `6e5544cfa3eecb8329e4f4cb19d2e0ac3e99b1bf`. The tested artifact's `SOURCE.json` binds both distributions to `0b13a2121014d8256954c6af50339ff0de8dac62` and release tag `v0.4.0-alpha.6`. Public PyPI metadata, filenames, sizes and SHA-256 hashes match that artifact exactly; the distributions are not yanked.

| Distribution | Bytes | Public and tested SHA-256 |
| --- | ---: | --- |
| [pystachy-0.4.0a6-py3-none-any.whl](https://files.pythonhosted.org/packages/e3/07/60e3b42a2425b92322441bddf9cfc8fc6441f2448ccbb8b1e5ec8b9e6346/pystachy-0.4.0a6-py3-none-any.whl) | 1,905,081 | `2fa743d550c39467f7b14fdd843f194596eb19e96fb9601cc1856a5fead8c04f` |
| [pystachy-0.4.0a6.tar.gz](https://files.pythonhosted.org/packages/4c/d8/03e9ebea1127f296456fa1e0bb13737b8a4703b7c6970e43a109872f731d/pystachy-0.4.0a6.tar.gz) | 1,833,275 | `735765db951ece2201447626287a296da9dfe03e613dd64151e9c0810bd8cc18` |

Fresh pip and uv installations used the downloaded public wheel in separate temporary environments outside the checkout, pinned CPython 3.13.16, and LLVM 19.1.7. Both passed version reporting with LLVM unavailable, JIT output comparison against CPython, standalone AOT execution with an empty PATH, external runtime and native JIT-runner cache checks, and clean uninstall. The source distribution also passed the exact-source distribution-content audit; hosted package qualification exercised its corresponding built outputs.

The wheel’s source identity is established by the tested source receipt and exact public byte equality. The installed version string is not used as evidence of an embedded source commit. Public-install evidence, including script and log hashes, is included in `audit.json` and `pypi-public-install-evidence.json`.

## Retained workflow artifacts

The downloaded ZIP for each of these seven artifacts matched GitHub’s advertised SHA-256 digest. Raw archives remain addressable by run/artifact ID; this compact report contains no temporary signed download URLs or credentials.

| Artifact | Artifact ID | ZIP SHA-256 |
| --- | ---: | --- |
| binary-linux-aarch64 | [13983316584](https://github.com/den-run-ai/pystachy/actions/runs/43303651615/artifacts/13983316584) | `59d278112d933aeaed3082cccba0d576cf43a00ca38c916b1dbe29be74958f1f` |
| binary-linux-x86_64 | [13983721188](https://github.com/den-run-ai/pystachy/actions/runs/43303651615/artifacts/13983721188) | `a2562e6bbe5523ea106feaac0a7e3508c801a00761a30313b178dc1038c986b3` |
| binary-macos-arm64 | [13982797256](https://github.com/den-run-ai/pystachy/actions/runs/43303651615/artifacts/13982797256) | `9cc9514a9b813578ae609ed15d8e3c186d7f02af82bb7351767424f49615875d` |
| binary-macos-x86_64 | [13984340841](https://github.com/den-run-ai/pystachy/actions/runs/43303651615/artifacts/13984340841) | `3fbc82b41f86fe23a3b24191874eb3c9a5b28bb4081e4df1352a50fdd96ec741` |
| container-linux-amd64 | [13982853529](https://github.com/den-run-ai/pystachy/actions/runs/43303651615/artifacts/13982853529) | `fbf16d7f69e0b6b015cdc6f21e5cc9c162499cf28665c48e1bb81c32656ee12d` |
| container-linux-arm64 | [13983298050](https://github.com/den-run-ai/pystachy/actions/runs/43303651615/artifacts/13983298050) | `eedbe531295daa2c9395454131d5d25606ad37c7772f5593af1da3de6aeca713` |
| pypi-0.4.0a6 | [13983773116](https://github.com/den-run-ai/pystachy/actions/runs/43306789202/artifacts/13983773116) | `844ff27e2b37ac45e2d89145f3236ebca978207b9be0fd0dbd406b295840a424` |

## Stable aliases and scope

GitHub’s latest release remained [v0.3.1](https://github.com/den-run-ai/pystachy/releases/tag/v0.3.1). Docker `latest` remained byte-identical at index `sha256:a9c31998280fc47c50fe401f2575fcefddc088f915615ac8f9ce8b8e1b41a953`, with both architectures still labeled v0.3.1 at `6e5544cfa3eecb8329e4f4cb19d2e0ac3e99b1bf`.

This report verifies publication identity and public artifact availability. The source qualification record, remaining RC stabilization issues, and broader v0.4.0 release decision are maintained separately. Alpha.6 publication does not itself close those outstanding items.
