# Independent final alpha.2 acceptance

**Accepted: v0.5.0-alpha.2 is published and verified across GitHub native assets, both native Docker architectures and PyPI.** Source `80490143498d149d407343ba1cb7aedb1db2d2c5`, tree `717a8c9386ae9f5f6545cc3686a9e22282fc560c`.

The native Release run `43626857296` passed eight jobs with two expected PyPI skips; the longest took 683.0 seconds. PyPI run `43630294045` passed both packaging/publication jobs with four expected native skips; its longest took 76 seconds. All executed jobs stayed within 15 minutes.

## Public distributions

- GitHub: https://github.com/den-run-ai/pystachy/releases/tag/v0.5.0-alpha.2 — all 11 public assets match tested artifacts.
- Docker: `dta67/pystachy:v0.5.0-alpha.2` — both native platforms, exact tested configurations, 11 downloaded public blobs and 14 verified layer references.
- PyPI: https://pypi.org/project/pystachy/0.5.0a2/ — public wheel and sdist match the tested/uploaded bytes. Every packaged source file is bound to the exact release Git blobs.

Actual publishing-workflow checks cover clean pip/uv installation, JIT, standalone AOT, external caches and uninstall. The additional local public-wheel checks used two fresh isolated environments, verified all 163 payload files per environment, correct package metadata and console version. The parent and child optimization context was recorded during those actual checks. Hosted wheels correctly print `pystachy v0.5.0-alpha.2 (commit unknown)` because their documented package contents contain VERSION and no REVISION; source identity comes from exact source-byte and distribution-hash checks.

## Qualification

All seven applicable exact-main workflows passed; their complete check inventory contains 131 successes and one expected PR-only skip. The complete Lean audit covers 2,550 programs, retains all 2,529 shared programs, adds 21 fully proved programs and 1,203 proved obligations, and records no new failed/unproved outcomes or coverage losses. The strict 175-program storage corpus proves all 18,582 obligations.

The retained 4,579-case compiler comparison has no new rejection and explains every substantive IR/diagnostic difference. Only three independent Lean checker/test files changed in the compared compiler-source trees, so that evidence remains applicable. Fresh exact-main performance has 49 `ok` comparisons. The separate three-workload warm-build experiment finds lower build time and recorded peak RSS with larger executables; size rises 4.9–35.6%. The separate fresh bootstrap observation increased from 155.481 to 162.397 seconds (+4.4%); it is one sequential pair without confirmation and does not establish a sustained change. These bounded measurements do not establish broad runtime or memory improvements.

## Review provenance

Two independent agents completed complementary compiler/class/typing/dispatch and driver/runtime-cache/verification reviews on the exact candidate tree, which equals the release tree. Neither found an actionable new defect. **GitHub Codex did not complete the four recorded service attempts, and the local CLI did not complete a review.** Its attempts ended at argument validation and read-only app-server initialization, with no workaround. The completed independent reviews are recorded separately and are not represented as successful GitHub/CLI Codex reviews. The sole historical review thread is resolved. A separate published-body review found no stale or unsupported release claim.

## Stable pointers and audit scope

The final public comparison confirms GitHub stable remains `v0.4.0` at `5f81cc2563d231501952104e991d858e670325ac`, PyPI stable remains `0.4.0`, and Docker latest retains `sha256:037f5691b17c9ae9a8afb6be79bf6870a1a81fb9ada67ec5e3d9dd5b08d60d01`.

Detailed final receipt: `alpha2-final.json`, SHA256 `7ac9e86a7d4d48482d7d2a55ae77015d04daf21381529008ea6eb50e9ebbbec3`. Supplemental public-install receipt: `public-pypi-installs-independent.json`, SHA256 `2de748d1353300673d7c000acaa7a10ef075ef694dac0b6dd8f5d60dff5e70e1`. Both bind the complete component evidence and preserve its scope and limitations.

This final audit read frozen evidence, verified hashes/source bindings and recomputed inventory/timing facts. It performed no network requests, downloads, polling, payload execution, installation, compilation, tests or proof reruns.
