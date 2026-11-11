# Verified main-merge equivalence

**The merge preserves the consumed sources and retained binaries. The earlier IR and performance evidence remains applicable through exact identity; its original commit labels remain unchanged.**

| Role | Commit / tree |
|---|---|
| Original reference | `b40ee875bf72b86804c4f5a300066f4f7c3eb20b` |
| Updated main | `a339ab3748a59d6e4da899f0f3f2d5965b95e5ba` |
| Measured candidate | `dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6` |
| Published integration | `601807e3686fa83a362cceb0d962d8e6332fbc34` |
| Local integration | `62b93c370d5bfa52f22199c31efcb6764b77e6f5` |
| Shared integration tree | `b28d80a94d0ac11e18cd6da7c6586e704a757bfd` |

Both integration commits have exactly two ordered parents: the measured candidate and updated main. Their trees are equal. The checked local tracked worktree is clean.

## What was checked

- **161/161 recorded measurement-source hashes** match the integration worktree and the candidate/integration Git blobs and modes.
- **146 additional native, benchmark, helper and configuration inputs** have matching candidate/integration blobs, modes and worktree bytes.
- Complete `src`, `lib`, `bench`, `examples`, `mpz`, `ryu`, `tests` and `ports` directory trees are identical from the measured candidate to integration. Their contents include benchmark data and imported fixtures outside the explicit measurement manifest.
- All **4,438 IR input paths** retain identical candidate/integration modes and blob IDs. Old and new main also have identical pre-existing inputs, as established in `match-main-update-equivalence.json`.
- The bootstrap recipe and match Makefile targets remain identical. Both the match correctness/artifact step and the newly added Lean gate/artifact are present in merged CI.
- The native compiler, old reference compiler and measured AOT executable were read and SHA-256 checked against their original reports; all are identical. No compiler or benchmark was executed.

| Retained binary | Original build provenance | Verified SHA-256 |
|---|---|---|
| native compiler | `dec4d9f1` | `39177cf908ec1b681ea133db3d830e5c9c12dff6ddbb7de46189166a913e74dc` |
| reference compiler | `b40ee875` | `915710b8f89d8473e8e0711267f16eec2f39119d6c81e63f102b22c3d2ae0c84` |
| measured aot program | `dec4d9f1` | `da6dcda2fa6ed927bed503f5e7ca6e079d15bd474fcf5db57bae65806246bc46` |

The preceding main-update proof records 303 individual unchanged old-main/new-main inputs, eight identical directory trees and unchanged LLVM package/version/checksum pins. The downloader changes connection recovery; new Lean tools change validation. These changes require their new CI checks but do not change the recorded native computation.

## Provenance and minimum remaining checks

Keep the IR record labeled `b40ee875` versus `dec4d9f`. Keep the completed seven-pair, 10,000-loop controller and its AOT executable labeled `dec4d9f`. Upcoming real pyperf measurements of that executable should preserve this build provenance, record the current checkout separately, and link this equivalence record. They are new measurements of the retained executable, not measurements retroactively performed at a different commit.

Require CI/lint on published integration `601807e3`, including the added Lean checks, updated downloader tests and existing compiler/runtime/match gates. A clean identity proof does not substitute for those new gates. If they pass without a relevant code change, the merge alone does not justify duplicating a reference build, full IR corpus or long timing campaign. Any new consumed-source, toolchain, binary, flag or corpus difference would require reassessing and rerunning the affected evidence.

The companion JSON stores exact per-file hashes, directory IDs, binary hashes, integration parents, original-report hashes and controller settings. Original IR/timing/build reports were not modified. Large LLVM tools were not rehashed as part of this source/binary check; their recorded identities remain in the original controller metadata.
