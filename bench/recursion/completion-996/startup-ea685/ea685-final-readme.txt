PR #996 final startup and fnmatch evidence for ea685
==================================================

Current main: 07b26e02425d023288ed95a9d2a5077be5aeb45e.
Candidate: ea68529b8a590eb8f3df7200b857e1d16becd7a3.
Historical reference: da84d382ff83f09e46d4ef104e62e6f64e9c37c1.

The evidence is complete. Performance acceptance remains open. Startup improved
over the handoff source, but the candidate still costs more than current main,
and the longer fnmatch AOT follow-up did not clear the local slowdown.

Completed, separately retained experiments
-----------------------------------------
1. Normal native-driver startup comparison: 108 observations, three workloads,
   JIT and AOT, three compiler roles, six balanced orders. All CPython checksums,
   fresh main/candidate bootstrap bindings and final identity checks passed.
2. Focused fnmatch AOT follow-up: 36 observations, n=10,000 and n=100,000, same
   already-built executables, six balanced orders with rotated size ordering.
   Both CPython checksums, six warmups and original-report/source/tool/executable
   identity checks passed. No rebuild or source change occurred.
3. Hosted inspection: six cells (object, JSON, mixed text; recursionregion on/off)
   matched ordinary hosted LLVM and compiler diagnostic streams exactly.
4. Exact driver augmentation: actual native opt input equals the inspected module
   plus the retained 140-byte target prefix and literal 299-byte OBJHOOKS suffix.
   Source AST, runtime/cache bytes, modules and profiles are hash-bound. Produced
   llvm-dis text was bound to its input bitcode at production. Constructor code
   remains in the structural inventory. The corrected v2 symbol join preserves
   printed names and permits only enclosing quotes around valid plain names.

Primary current-main comparisons
--------------------------------
Complete opt+lli instructions are 10,005,501,078 for main and 10,961,454,947 for
the candidate: +9.5543%. Candidate work is 6.0713% lower than historical da84.
These totals include lli program/runtime execution, not only code generation.

JIT whole-process candidate/main, percent:
                  ratio of medians   median paired ratio   slower pairs
  fnmatch              +12.90              +12.50                5/6
  JSON                  +5.72              +11.19                5/6
  repair_scan           +5.05              +13.14                5/6
Candidate process medians improve 8.39%, 7.97%, 8.91% over da84 respectively.
Outside-loop wall time includes frontend, LLVM, initialization and teardown.

Original short AOT loop candidate/main, percent:
  fnmatch: +17.61% by medians, +9.24% paired median, slower 6/6 pairs.
  JSON:     -0.54% by medians, -0.76% paired median, slower 3/6 pairs.
  repair:   +4.55% by medians, +9.74% paired median, slower 3/6 pairs.
All samples and wide ranges remain in the records; none was discarded.

Focused fnmatch AOT loop follow-up:
  n=10,000: main 0.251212s, da84 0.262699s, candidate 0.264405s.
    Candidate/main +5.25% by medians, +3.72% paired; slower 4/6 pairs.
    Candidate/da84 +0.65% by medians, +3.70% paired.
  n=100,000: main 2.551652s, da84 2.724147s, candidate 2.764386s.
    Candidate/main +8.34% by medians, +8.86% paired; slower 4/6 pairs.
    Candidate/da84 +1.48% by medians, +3.57% paired.
    Whole-process CPU also rises +8.95% by medians, +9.42% paired versus main.
The cost remains at longer durations. CI's same-source n=1,000 fnmatch AOT result
is +1.21% on AMD EPYC 7763 with three samples; this local Intel Xeon 8573C series
is separate. Neither result overrides the other. No acceptance threshold is
invented, and the two elapsed experiments are not pooled.

Structure and limitations
------------------------
Mixed-text region specialization adds 55 functions and 5,790 private-body typed
operations while original rewrites remove 1,852, for net +3,938 operations.
Raw hosted LLVM grows from 73,727 to 79,703 lines. The number scanner remains
573 optimized lines; its partial child is inlined into the value/scalar_value
paths, which have 1,109/1,019 optimized lines. This structural evidence does not
attribute tool instructions or time to individual functions or identify refusal
reasons. Shared-host elapsed variability remains despite exclusive team windows.
Historical da84 instruction profiles passed exact current-control reuse checks;
their old manifest did not separately hash the historical LLVM/clang libraries.

Reproduction and file layout
----------------------------
Preserve publication-ea685-final.json relative paths under one startup-ea685/
folder. Follow reproduce-ea685.txt for the main native series. For the focused
follow-up, run fnmatch_followup.py prepare and then timings with --startup-report
pointing to the immutable startup report and --output set to a new directory.
Each timing phase requires a separately coordinated quiet window.

Use inspect_series.py capture for hosted evidence and link_inspection_backend_v2.py
for linkage. The capture controller's unused literal-link phase omitted driver
additions and was never run. The first separate linkage proved augmentation but
compared printed spellings; its symbol join is superseded by v2. The historical
hosted summary says linkage was pending because it was frozen before linkage.
The final export explicitly labels those snapshots; it does not rewrite them.

curated-ea685-final.json contains both full observation sets and vectors, source/
tool/build identities, profile bindings, exact CI fnmatch samples, and historical
record references. All raw LLVM/bitcode/profiles/executables remain locally
retained with hashes for the archive. No older missing diagnostic export is
claimed to have been recovered.
