# Stored enum exit status: local qualification

The isolated correction is commit **395227b75bb777401627c0296a18fe71388070e7**, tree **066f5a791216fc721d734bb1e23bdd6194bce42f**, on `followup/sys-exit-intenum-stored`. The source worktree is clean. No source branch, PR, comment or release was pushed or published by this workstream. The frozen RC.1 source was not changed.

The implementation corrects the stored integer status of `IntEnum`, `IntFlag` and supported `int, Enum` members, including aliases, computed flag members, base-typed values, caught or stored `SystemExit`, and `SystemExit` subclasses. Local native qualification passes. Fresh source-pinned hosted PR/full-GC qualification is still required for an RC.2 integration tree; this report is not full release qualification.

## Why the original proposal needed a correction

The original PR [#1392](https://github.com/den-run-ai/pystachy/pull/1392), at `78b7c5422b00d006013e3de4d1f3b77623b07122`, fixes the baseline's treatment of enum objects as exit messages by calling `__index__`. That call can execute a user override and select a different status. It does not reproduce CPython's handling of an existing integer object.

CPython 3.13.16's [`parse_exit_code`](https://github.com/python/cpython/blob/v3.13.16/Python/pythonrun.c) checks whether the code is an integer object. [`PyLong_AsLongLong`](https://github.com/python/cpython/blob/v3.13.16/Objects/longobject.c) reads such an object's stored integer directly; the conversion protocol is for other objects. The source files and their SHA-256 hashes are retained in `source-provenance.json`.

The execution controls establish both problems:

| Probe | Pinned CPython | Frozen baseline | Original PR, native JIT and AOT | Corrected native JIT and AOT |
|---|---|---|---|---|
| Zero-valued member whose `__index__` prints and returns 7 | Status 0, stdout `bye\n`, no stderr | Status 1, stdout `bye\n`, stderr `0\n` | Status 7 and an extra `index called\n` | Exact CPython result |
| Zero-valued member after assigning `_value_ = 7` | Status 0, stdout `7\n`, no stderr | Status 1, stdout `7\n`, stderr `7\n` | Status 7 | Exact CPython result |

The repository's enum contract and implementation were reviewed before adding storage. `_value_` is mutable metadata. The class tag and `_name_` do not hold the original numeric value, and computed flags have no suitable static member constant. There was no existing immutable integer payload to reuse.

## Representation and visibility

One compiler-owned `int` slot is added to the `IntEnum`/`IntFlag` representation and inherited by their supported descendants. Canonical member creation initializes it from the original integer. Computed flag creation initializes it from the new member's integer. Aliases retain the same object. Exit lowering reads that slot directly and neither calls `__index__`/`__int__` nor reads mutable `_value_` for status.

The initial local draft `5cba0c6f` exposed this slot through literal reflection. Independent review found that `setattr(member, " enum int", 7)` overwrote the status. The retained native negative control confirms the faulty draft printed `True\n7\n` and exited 7 in both JIT and AOT, while CPython printed `False\n7\n` and exited 0.

The final correction closes that access at the public field boundary. `hasattr` stays false, and `getattr` with a default still evaluates and returns the default, including its side effects. Literal setter and direct-getter attempts retain the baseline's existing unsupported/missing-attribute diagnostics. Constructors and exit lowering use internal slot addresses. `dir`/`vars` inventories already omit internal slots. Dynamic-`Any` boxing of these int-like enum objects remains rejected by the existing admission rules. The correction does not add a general reflection restriction.

### Measured size and GC implications

LLVM 19's x86-64 datalayout and constant-folded `getelementptr(T, null, 1)` give these requested object sizes:

| Representative layout | Baseline bytes | Corrected bytes |
|---|---:|---:|
| `IntEnum`, integer mixin, `IntFlag` base | 40 | 48 |
| Wide-value `Status` in a promoting-integer module | 56 | 64 |
| Reflection fixture's `Status` and computed `Perm` | 64 | 72 |
| Library fixture's `Num` | 72 | 80 |

Each measured layout grows by eight bytes. These small requests also move by one eight-byte allocator class under the current allocator's slack-byte rule. `layout-sizes.json` distinguishes LLVM measurements from that source-derived allocator calculation; it is not a heap profile. Larger custom layouts retain the allocator's existing coarser size classes.

The new slot is a fixed 64-bit scalar. It creates no additional referenced object, assignment flag or identity box. The object keeps its existing scanned allocation behavior. Inheritance offsets, assignment flags and existing numeric identity boxes are retained after the new slot. The promoting-integer probe uses a supported signed-64-bit enum value outside the small tagged-integer range; this change does not broaden enum values to arbitrary-width integers.

## Provenance and integration

| Local commit | Purpose |
|---|---|
| `440b7a0966b6baa4e0ab7163ff6456d94cdf5770` | Genuine `cherry-pick -x` of original PR head `78b7c5422b00d006013e3de4d1f3b77623b07122`; original author/provenance retained |
| `5cba0c6f9450bb7185e6882103d42deb7e132912` | Separate original integer payload, direct exit-status reads and differential regressions |
| `395227b75bb777401627c0296a18fe71388070e7` | Public reflection boundary and accepted-probe/rejection controls |

The local baseline is `7c75948747090c7d6a0a0bf76f9aecee8de90a15`, tree `64f1fb7295efd25401052d61a22823681e5669ab`. Its compiler identity comes from the root's retained receipt. The receipt was recorded after bootstrap, rather than as a contemporaneous sealed CI bundle; that limitation is preserved.

An independent `git merge-tree --write-tree` check of that baseline and the original PR head yields `7437c4e991bcd501ecf8a099e74be241b3232459`, exactly the first local cherry-pick's tree. This supports the root's integration plan to preserve original PR history on a separate branch, followed by the two corrections with exact tree assertions. `provenance-merge-tree.json` records the check. The original PR branch is untouched.

Compiler/library/runtime object identities of the final tested source are recorded in `source-provenance.json`. A subsequent VERSION/release-note-only commit can retain those source objects, but its final versioned tree still needs fresh CI qualification.

## Qualification results

Toolchain: CPython **3.13.16**, LLVM **19.1.7**, Linux x86-64. Compiler/runtime caches were private. Native test concurrency was at most two workers; bootstrap used one build. Source was frozen during all builds and qualification runs.

| Check | Result |
|---|---|
| Fresh compiler bootstrap | Passed: three IR stages identical, 915,570 lines |
| Fresh runtime bootstrap | Passed: three IR stages identical, 21,214 lines; runtime IR matches the baseline byte-for-byte |
| Exact status, full stdout and full stderr | 96/96 passed: 24 cases × JIT/AOT × normal/GC stress |
| Related normal corpus | 70/70 passed: 20 program cases in both modes and 30 rejection cases |
| Related program GC stress | 40/40 passed: the same 20 programs in both modes |
| Full typed-IR and LLVM assembly check | All 2,569 non-rejection corpus inputs accepted |
| Pinned CPython recording verification | 2,336 recordings, 130 deviations and 11 stdlib copies checked; zero failures |
| Pinned agent-source verification | Six files verified at `9256333b07628f6e4b399f41916f36d463914501` |
| Changed-file Ruff check | Passed with pinned Ruff 0.17.3 |
| Full retained compiler comparison | 4,481 valid results; 2,569 accepted and 1,912 rejected on both sides; zero new rejections, acceptances or compilation status changes |
| LLVM19 runtime-table checker | **Not a pass:** the same 57 findings as the retained baseline, byte-for-byte |

The recording check initially lacked `typing_extensions` in the newly installed Python environment. Its five affected programs produced ten failures, all reporting that missing dependency. The failed run is retained. After installing the repository's pinned `typing_extensions==4.16.0` into a private CPython 3.13.16 environment, the full recording check passed without changing expected outputs. An initial runtime-check invocation also omitted the LLVM path; that setup failure is retained separately from the correctly configured, baseline-identical checker result.

The final native compiler SHA-256 is `cec4a5470dce6ad3cb6358b9b47552609b799e401fad1385e23a31a9af0571fc`. Its three compiler IR stages hash to `2a83de6978d9a1bbf15200c3de3c78e3bbaceaeb69fae258b8a6e9f376db82e0`. The three runtime IR stages hash to `cd645bebc4fea57b4824b5393843fea99bb31880a31a79dd825e1f34c388f830`.

## Retained comparison adjudication

The oracle uses the repository's full `irsame.sh` corpus and the exact existing conservative diagnostic-normalization functions. Each compiler reads its own library. No IR is normalized. All raw IR is retained losslessly as `.ll.gz`, and every raw diagnostic, normalized diagnostic, result and IR diff is retained by case index under `ir-comparison/cases`.

There are **283 oracle differences**, comprising 269 IR differences and 14 diagnostic differences that survive official normalization. Another 56 raw diagnostic differences are already handled by that official normalization. All 70 raw diagnostic differences are exact substitutions of the respective compiler's own checkout home, with no status/message-content change beyond that location.

| IR category | Cases | Evidence |
|---|---:|---|
| Checkout-path string literals only | 237 | Exact home substitution, unchanged symbol/hash, independently checked character counts, byte counts and both LLVM array bounds |
| Unused enum base type declarations plus checkout paths | 4 | Only the three reviewed `IntEnum`/integer-mixin/`IntFlag` layout declarations change |
| Enum library layout and initialization | 14 | Every global, type, TBAA node and all 1,249 functions accounted; 42 private-payload stores verified to duplicate the member's original value store |
| Exit-specific enum paths | 14 | Independent per-case review found no additional issue; all 28 retained old/new IR hashes verified |

The library-case audit accepts only the reviewed scalar insertion, field-index/TBAA adjustment, a verified duplicate initial-value store, and SSA/block renumbering. It does not discard arbitrary operations. This is an explanation of the retained raw differences, not a replacement for the raw oracle. `ir-adjudication.json`, `layout-function-review.json` and the independent exit review provide the per-case records.

## Explicit boundary and remaining gates

**Eager exception formatting remains a documented deviation.** For a zero-valued member whose `__str__` prints, CPython exits 0 with `finally\n`; the corrected compiler exits 0 with `str called\nfinally\n`. Both native modes reproduce that difference, with empty stderr. This work fixes the status and does not claim lazy formatting or a full-output match for that probe. `native-negative-controls.json` records the full streams and marks the known deviation explicitly.

The LLVM19 runtime checker still reports its 57 baseline findings; their diagnostic-lines SHA-256 is `58066a522a11e6f51fc793c42cb8dc139e767ab1fabe7d6b431fb62206f52c80`. Required hosted LLVM18 checks are outstanding for the follow-up. No local full-verify claim is made: full GC groups, sanitizer/distribution/embedding matrices, alternate architectures and final release artifacts require the final RC.2 workflow qualification. No performance timing claim is made for this enum correction.

The independent review of all 14 retained exit cases is complete and found no additional issue. All 283 oracle differences, and the additional 56 diagnostic differences already handled by the official normalizer, are accounted for. The evidence supports proceeding to an isolated RC.2 integration checkpoint and fresh CI. It does not treat an unqualified integration commit as release-ready.
