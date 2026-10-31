# PR #996: current-main validation and remaining performance decision

The continuation integrates PR #1000, reduces backend work compared with the
archived PR source, and completes a fresh validation and measurement series on
current main. **PR #996 remains draft. Performance acceptance is still open.**
The longer AOT fnmatch experiment continues to show overhead; green correctness
checks do not resolve that decision.

This report and its raw records live on the separate research evidence branch.
They are not changes proposed for merging into main.

## Evaluated revisions

| Role | Commit | Tree |
|---|---|---|
| Current main, including #1000 | `07b26e02425d023288ed95a9d2a5077be5aeb45e` | `9996e386de938ba299410aef49bd5bc4aa27abca` |
| Evaluated PR candidate | `ea68529b8a590eb8f3df7200b857e1d16becd7a3` | `62ad6bb99fbc3e1625f36f167d664f2d8f221801` |
| GitHub synthetic merge used by CI | `f5c491ddf1627a35a715ae71167fb5c5126309de` | `62ad6bb99fbc3e1625f36f167d664f2d8f221801` |
| Archived PR reference | `da84d382ff83f09e46d4ef104e62e6f64e9c37c1` | `903a72dce156018f83f69f1e8b4d74a6f14e99dd` |

The candidate is a merge of the previous `db14f824` PR head and current main.
The published tree equals the integrated local tree, including the hosted
observer extension. [Publication binding](../../bench/recursion/completion-996/candidate-ea685/publication-binding.json)
records exact tree and file identities. Historical measurements below retain
their original source labels; they are not presented as reruns of this candidate.

## Changes made after the handoff

The PR retains its catchable logical recursion-depth guard, checked fallback,
bounded and partial recursion paths, generator/unwind handling and conservative
lifetime exclusions. This continuation makes four compiler changes:

1. Checked original leaves can share an already proven bounded `@rf` body, or an
   available `@rc` body. The wrapper uses an exact-signature `musttail` transfer,
   including hidden numeric-identity operands. Tuple returns remain excluded.
   The private body owns the copied slots; slot-bearing source functions were
   already eligible when the wrapper's lowering invariants hold.
2. Nonthrowing depth, restore and room operations lower directly to LLVM while
   retaining their typed effects and alias metadata.
3. A successful counted child can prove room for a later leaf call while the
   caller keeps its own logical frame published. A conservative control-flow
   must-analysis retains the first guard and invalidates the proof across
   unknown, foreign and generator effects. It adds no runtime cache.
4. Eligible check/enter helpers use ordinary LLVM inlining decisions. Programs
   blocked by lifetime constraints retain mandatory inlining. The policy is
   captured before optimization and exception lowering; scalar helpers retain
   their existing handling.

After merging #1000, the CPython-only inspector also observes the whole-program
`recursionleaf()` and `recursionregion()` passes. Its symbol-keyed before/after
union includes newly added and removed private functions, operation/slot counts,
recursion metadata, actual pass return units and the actual lowering policy.
It does not invent refusal reasons. Tests verify exact observed/unobserved LLVM
and diagnostic parity. The observer itself is not part of the native compiler.

Rejected trials remain evidence: preliminary cleanup, broader partial outlining,
lazy ORC startup, and a broader alias/MemorySSA change did not justify adoption.
The alias trial also had an unsafe foreign-call counterexample. The archive and
source-reconstruction records distinguish these trials from the evaluated code.

## Correctness evidence on the evaluated candidate

| Evidence | Result and scope |
|---|---|
| Fresh local main bootstrap | Three compiler and runtime IR stages agree; native stages agree; all consumed inputs stayed fixed. |
| Fresh local candidate bootstrap | Same fixed-point and input-identity checks, with a newly built candidate binary. |
| Focused native execution | Six affected fixtures in JIT and AOT with `PYSTACHY_JIT_INLINE=0`, plus scoped-file JIT GC stress: 13 executions passed. |
| Local hosted validation | 522 tests, Ruff and mypy passed. The two compiler-state subsets cover all 108 state tests. |
| Hosted inspector parity | Six object/JSON/mixed-text cells, with region specialization on and off, match ordinary hosted LLVM and diagnostic streams exactly. |
| Full current-main compilation comparison | 3,924 cases recorded: 2,140 programs and 1,784 expected rejections; no missing cases, validation failures or changed exit statuses. Diagnostic review is described below. |
| Current-head CI | 59 successful checks and two expected skips; all seven workflows complete. |

The local candidate compiler's SHA256 is
`f00814e63cf2fecedf2f1f6dac8dc1aae714744d0357fdc58e59d68afcf4b84e`.
Its compiler IR has 808,317 lines and SHA256
`4c64d1337da57bc0d88b936d19e9e49da5bf74c241092d80f37621e96e2ac5f1`.
The fresh main compiler IR has 775,228 lines. Both runtime fixed points have
18,805 lines and SHA256
`940a694da5ea93214d1308a8eb635b47d8d0a9d4256c63d084c24f5099f8aa5f`.
The CI compiler IR matches the local candidate IR; CI's native binary has its
own recorded identity and is not relabeled as the local build.

The CI collection independently remerged all 31 original verification reports,
covering 54 logical stages and 84 group-stage records. All 37 downloaded ZIPs
passed hash, size and CRC checks. Lint ran all 32 expected unittest commands
exactly once: 919 tests, zero unittest skips. That includes 213 typed-IR tests,
20 inspector tests, eight diagnostic-capture tests and 108 compiler-state tests.
Mypy checked 48 source files. The local and CI test totals overlap and must not
be added together. The two expected workflow skips are same-repository DCO and
main-only coverage-badge publication.

See [current CI explanation](../../bench/recursion/completion-996/ci/README-ea685.md),
[CI summary](../../bench/recursion/completion-996/ci/ea685/summary.json),
[hosted validation](../../bench/recursion/completion-996/candidate-ea685/hosted-validation.json),
[native fixtures](../../bench/recursion/completion-996/candidate-ea685/native-fixtures.json),
and the two [fresh candidate](../../bench/recursion/completion-996/candidate-ea685/bootstrap.json)
and [fresh main](../../bench/recursion/completion-996/current-main-07b/bootstrap.json)
bootstrap records.

### Full corpus diagnostic review

The frozen comparison uses each compiler's own verified library home while both
read the same candidate corpus. Main has 3,903 planned cases; the candidate adds
21 and removes none. All candidate cases were exercised by both compilers.
Raw LLVM changes are expected and retained: 2,139 of 2,140 accepted programs
produce different raw IR. This comparison does not claim byte-identical IR or
runtime equivalence.

The original strict run returned exit status 1: 61 raw diagnostic pairs differ,
32 passed its narrow checkout-prefix proof, and 29 remain flagged. There are
zero changed compiler exit statuses or case-validation failures. The original
failed report is immutable. The
[separate assessment](../../bench/recursion/completion-996/candidate-ea685/corpus/assessment.json)
proves all 29 remaining pairs differ only in own-checkout prefixes embedded in
specialization/call-stack locations. It validates 74 source-location tokens per
role across ten byte-identical library files, with the same relative paths and
line numbers and exact equality of every residual message byte. Each file
matches both the original input manifest and its pinned committed Git blob.
An independent byte-span replay passed for every pair. There are no remaining
unexplained diagnostic differences; the original strict gate is still recorded
as failed, alongside this reviewed environmental explanation.

## Performance: complete tool work and process startup

The current series uses LLVM/Clang 18.1.3, CPython 3.13.16 and Valgrind 3.22.0
on an Intel Xeon Platinum 8573C host. Elapsed processes are pinned to CPU 0.
Team-owned heavy work was stopped during measurement windows, but the shared
host still introduces variability. Six balanced role orders are retained for
each workload and mode. No samples are removed and no significance claim is
made. The primary elapsed series uses prepared runtime caches; first-use cold
and warm preparation observations remain separate and are excluded from its
acceptance statistics.

The complete-tool instruction profiles are:

| Work | Current main | Candidate | Candidate/main |
|---|---:|---:|---:|
| `opt` | 1,674,260,324 | 1,846,555,997 | +10.29% |
| `lli` | 8,331,240,754 | 9,114,898,950 | +9.41% |
| Combined | 10,005,501,078 | 10,961,454,947 | **+9.55%** |

The candidate's combined count is **6.07% below archived da84**. The `lli` count
includes executed program, runtime, GC and teardown work; it is not a pure
code-generation or startup count. Historical profile reuse is separately
hash-bound and its limits remain in the record.

The [remaining-cost assessment](../../bench/recursion/completion-996/startup-ea685/remaining-cost-ea685.txt)
finds that `lli` accounts for about 82% of the current-main instruction delta.
Its machine-function pass work increases by 636.5 million inclusive instructions.
SelectionDAG and register-allocation counters are nested within broader pass
work and must not be added together. The final mandatory-inliner total is only
29.2 million inclusive instructions, so it is no longer the dominant hotspot.
These JIT profiles do not identify the cause of the separately measured AOT
fnmatch loop regression.

All 108 primary elapsed observations passed their CPython checksums and final
source/build/tool identity checks. These are JIT whole-process comparisons:

| Workload | Ratio of process medians | Median of within-round paired ratios | Candidate slower |
|---|---:|---:|---:|
| fnmatch | +12.90% | +12.50% | 5/6 |
| JSON | +5.72% | +11.19% | 5/6 |
| repair_scan | +5.05% | +13.14% | 5/6 |

Both statistics are reported because shared-host variation makes them differ.
Against da84, process medians improve 8.39%, 7.97% and 8.91%, respectively.
Outside-loop wall time includes frontend compilation, LLVM, initialization and
teardown, so it is not attributed entirely to the backend.

### Longer AOT fnmatch follow-up

The original short fnmatch AOT loop was slower in all six pairs: +17.61% by
loop medians and +9.24% by paired median. A separate follow-up used the same
hash-bound executables, with no rebuild or source change, and 10x/100x larger
inputs. Both CPython oracles, six warmups, all 36 observations and final identity
checks passed.

| Iterations | Main loop median | Candidate loop median | Ratio of medians | Paired median | Slower pairs |
|---|---:|---:|---:|---:|---:|
| 10,000 | 0.251212 s | 0.264405 s | +5.25% | +3.72% | 4/6 |
| 100,000 | 2.551652 s | 2.764386 s | **+8.34%** | **+8.86%** | 4/6 |

At 100,000 iterations, whole-process CPU time rises 8.95% by medians and 9.42%
by paired median. Candidate/da84 loop medians are +0.65% and +1.48% at the two
sizes. The longer runs do not clear the local execution-cost concern.

CI's same-source fnmatch AOT smoke result is +1.21% at `n=1000`, with three
samples on AMD EPYC 7763. It remains a separate machine/sample series. CI JIT
whole-process medians are +13.35% fnmatch, +12.30% JSON and +11.83% repair.
Neither the local nor CI series overrides the other, and successful smoke
completion is not performance acceptance.

The [startup export](../../bench/recursion/completion-996/startup-ea685/curated-ea685-final.json)
retains both complete observation sets, absolute vectors, ratios, counts, builds,
tools, profiles and CI comparison. Its
[README](../../bench/recursion/completion-996/startup-ea685/ea685-final-readme.txt)
explains historical limitations. Use the subsequent
[reproduction audit](../../bench/recursion/completion-996/startup-ea685/reproduction-ea685-audit.txt)
for authoritative commands and dependencies; it supersedes stale planning and
linkage instructions without changing any measurement or controller bytes.

## Performance: execution kernels

The separate kernel series has 252 elapsed processes and 24 instruction-count
observations. It verifies CPython checksums, exact hosted/native input LLVM,
JIT/AOT results and final identities. Counts cover eight complete kernel calls,
including warmup and runtime/GC, with compilation, printing and timers outside
collection. They are not downstream machine-code equivalence claims.

| Kernel | JIT instruction overhead | AOT instruction overhead |
|---|---:|---:|
| Ordinary calls | +0.0001% | +0.0002% |
| Object calls | +0.0012% | +0.0011% |
| JSON | +3.3253% | +1.7474% |
| Managed-file JSON | +3.3908% | +1.7613% |

Ordinary/object counts exactly match da84. JSON improves relative to da84 while
retaining measurable overhead against current main.

Short loop medians are about 7–21 ms and often have broad paired ranges. The
longer JSON measurements are more useful context, though still variable:

| Case/mode | Main median | Candidate median | Paired median change | Observed paired range |
|---|---:|---:|---:|---:|
| Warmed JSON, JIT | 70.19 ms | 71.99 ms | +3.13% | −17.27% to +19.88% |
| Warmed JSON, AOT | 68.09 ms | 69.50 ms | +0.93% | −9.90% to +26.32% |
| Managed-file JSON, JIT | 73.77 ms | 76.10 ms | +3.46% | −0.44% to +4.69% |
| Managed-file JSON, AOT | 64.78 ms | 68.99 ms | +6.54% | −2.50% to +23.10% |

These are observed ranges, not confidence intervals. The complete
[kernel record](../../bench/recursion/completion-996/kernel-ea685/measurement.json),
[paired analysis](../../bench/recursion/completion-996/kernel-ea685/analysis.json)
and [method README](../../bench/recursion/completion-996/kernel-ea685/README.md)
retain every observation and collection boundary.

## What the new observer establishes

Mixed-text region specialization adds 55 private functions: 33 `@rf`, five
`@rp`, four `@rp2` and 13 `@rc`. Private bodies add 5,790 typed operations while
original-function rewrites remove 1,852, leaving a net increase of 3,938 and
286 slots. Raw hosted LLVM grows from 73,727 to 79,703 lines.

The leaf pass transforms 64 functions, reducing enter operations from 200 to
145 and restore operations from 443 to 349, while retaining 64 checks. The
actual guard policy observed in all six cells is ordinary inlining.

The number scanner retains 573 optimized LLVM lines; the partial child is
inlined into value/scalar-value paths of 1,109/1,019 lines. These structural
counts identify places to inspect, but do not attribute time or instructions
to a particular private function.

The [corrected linkage proof](../../bench/recursion/completion-996/startup-ea685/inspection-ea685-backend-link-v2.json)
binds the actual native driver input exactly to a 140-byte target prefix, the
inspected module and the literal 299-byte source `OBJHOOKS` suffix. Runtime
cache bytes, bitcode and disassembled text are bound to production records.
The v2 symbol join handles enclosing LLVM quotes without changing module bytes.
The earlier quoted-name join and pre-linkage snapshot remain explicitly
superseded historical records.

## Historical failures and preservation

The evidence retains the initial `156fc` bootstrap failure, successful `8ca9`
checkpoint, `860b` CI failure from stale guard-attribute expectations, and its
`db14` correction. The local db14 build is explicitly an equivalent-input reuse
of the preserved 860b build, not a fresh compilation. The old db14 kernel run
completed preparation and counts only; it has no elapsed phase and uses the
former `06e3` main. The current `ea685` candidate and `07b` main were rebuilt
and measured afresh.

Previously unpublished da84 validation and backend evidence is preserved in
research commit `1b7080e164ab68a8fcde042162428d9131c9f533`. The original missing
`recursion-region-startup-diagnostics.json` remains missing: 85,660 bytes,
SHA256 `8d4ccaa64ec19cd39484db48e28eae7a4d7ca91edbf8cc5b6955bae267c00503`.
Neither the new observer nor this continuation claims to recover that file.

The [publication manifest](../../bench/recursion/completion-996/publication-manifest.json)
binds the selected records and controllers. Raw case IR, profiles, executables,
caches and detailed logs are retained separately for recovery. The original
three archives remain dependencies for historical builds/toolchains; the
continuation does not silently rewrite frozen absolute paths.

## Remaining decision

The existing performance hold remains in force. The archived source's roughly
15% startup regression was not accepted; no replacement numerical budget has
been agreed. The current candidate improves that source, but still has roughly
9.55% extra complete-tool instructions, 11–13% paired JIT process overhead and
8.86% paired overhead in the long fnmatch AOT series on this host.

Those measurements require an explicit acceptance decision or further targeted
optimization. PR #1000's handoff supplies observability, not performance
acceptance or merge authorization. The PR must not be described as merge-ready
solely because its correctness checks are green. The recorded GitHub readiness
snapshot has no review submissions or review threads; the required maintainer
review remains separate from local engineering review. Recheck the live head,
main and every applicable check before any later authorized merge.
