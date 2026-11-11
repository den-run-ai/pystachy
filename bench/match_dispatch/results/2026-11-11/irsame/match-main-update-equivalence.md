# Main-update provenance and minimum integration checks

**The existing reference and measurements remain source-applicable after this main update, provided the final merge preserves the verified inputs. Keep their original commit and binary labels.**

Compared base `b40ee875bf72b86804c4f5a300066f4f7c3eb20b` with new main `a339ab3748a59d6e4da899f0f3f2d5965b95e5ba`. Final measurements were produced at `dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6`. The future integration commit has not been relabeled or assumed verified.

## Exact identity findings

The eight complete Git trees `src`, `lib`, `bench`, `examples`, `mpz`, `ryu`, `tests` and `ports` are identical between the old and new main commits. The companion JSON records their exact object IDs and **303 unchanged input files** with modes, Git blob IDs, SHA-256 and sizes:

| Input category | Files |
|---|---:|
| invocation configuration | 7 |
| benchmark sources | 127 |
| library | 90 |
| runtime native support | 12 |
| compiler | 56 |
| measurement oracle helpers | 11 |

All **161 source hashes** recorded by the completed final match controller match `dec4d9f` in Git. None intersects new main's 34 changed paths. Every one of the **4,438 IR input paths** is unchanged between old and new main where it existed; newly added match inputs are absent from both main versions. The compiler binary recorded by the IR and final timing controllers is the same: `39177cf908ec1b681ea133db3d830e5c9c12dff6ddbb7de46189166a913e74dc`.

The Makefile bootstrap recipe and compiler source list are unchanged. New Makefile commands add validation. New main changes Lean analyzers, their observer/tests, CI configuration and documentation; these are not inputs to the native compiler, runtime or measured dispatch program.

`pystachy_toolchain.py` **does change**. Its changes affect download retries, mirror fallback and failure messages. Ubuntu/macOS versions, package checksums, tool lists, archive pins and existing-toolchain checks remain unchanged. The measured native path uses the explicit `PYSTACHY_LLVM` recorded in its metadata; neither the native compiler nor benchmark metadata lookup calls the installer. This supports retaining the existing measured toolchain, but does not qualify the new downloader itself.

## Minimum honest integration work

1. After merging, record the actual commit/tree and prove equality against `dec4d9f` for the recorded 161 files, the eight directories above, and direct native/harness inputs. Verify the existing compiler/AOT executable hashes. A separate equivalence record can connect that integration commit to the earlier evidence.
2. Require CI on the actual integration revision, including new Lean checks and updated installer tests. Existing match correctness and ordinary compiler/runtime gates must remain enabled. Treat any new Lean rejection as a result to investigate, despite unchanged compiler code.
3. Preserve the original `b40ee875` reference and `dec4d9f` measurement metadata. Say that they apply through verified input equivalence; do not rewrite a report to claim it measured the integration commit.
4. If identity checks pass, the main update alone does not require another reference build, full IR run or long timing campaign. Use required CI's bootstrap and correctness checks as the integration rerun. Repeat expensive work only if a relevant source, binary, toolchain, flags or corpus check differs.

The source proof is not a new performance experiment and does not predict identical wall times. New gate results, final integration identity and binary provenance remain distinct evidence. The companion JSON contains exact input hashes, the recorded toolchain metadata, upstream changed paths and the original measurement-report hash.
