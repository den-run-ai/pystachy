# Independent review of recorded compiler-stage costs

Reviewed the two existing JSON reports, the measurement runner, the inspector's timing/publication code, and the draft research README. No new build, test, timing run, or compiler invocation was performed.

## Finding and action

The data supports a small, repeatable increase in native self-compilation peak memory and binary size. It does not establish a wall-time regression or speedup. No compiler change is justified from these timing samples alone. The draft is appropriately cautious overall, but the statement that FFI inspection RSS was unchanged needs a stronger methodological qualification.

### Supported bounded costs

| Metric | Original PR / full | New / finalize only | Interpretation |
| --- | ---: | ---: | --- |
| Native self IR median peak RSS | 902,728 KiB | 915,408 KiB | +12,680 KiB = 12.38 MiB, +1.405% by separate medians. All five paired increases are between 1.397% and 1.408%. |
| Native self GC-reported heap peak | 875.2 MiB | 888.7 MiB | +13.5 MiB, consistent in every recorded sample. This corroborates a real peak-memory increase rather than wall-time noise. |
| Native self GC behavior | 14 collections; 192.6 MiB live at the last collection | Same | No measured increase in this final-live figure or collection count. These are not allocation counts or a leak test. |
| Native binary bytes | 6,724,320 | 6,729,184 | +4,864 bytes, +0.0723%. |
| Library inspection median reported peak RSS | 318,252 KiB | 315,540 KiB | A repeatable 2,712 KiB decrease, approximately 0.85%, for this instrumented CLI workload. |

Retain the self-memory increase in the PR's cost disclosure. It is small relative to the roughly 882–894 MiB observed process peak but should not be dismissed as timing noise. The records do not identify its cause or show how it scales to other inputs.

## RSS limitation requiring clearer wording

Every native FFI sample reports exactly **20,100 KiB**; every hosted FFI inspection sample, including both warmups, reports exactly **231,768 KiB**. The latter samples run after the long-lived measurement process has read and decoded the 67,793,315-byte library snapshot.

`wait4` avoids the cumulative `RUSAGE_CHILDREN` maximum, but its `ru_maxrss` can still include memory before exec. Linux preserves the previous address-space high-water mark during exec; the fork path also initializes the child's high-water mark from its copied address space. This creates a possible inherited runner-memory floor for a small target. The exact constant FFI figures, and their large difference between the native and post-library inspector phases, are consistent with that limitation. The recorded data contains no independent post-exec RSS observation to resolve the workload's own peak.

Suggested replacement for the draft sentence:

> Library inspection's reported process high-water mark decreased by approximately 0.85%. The FFI inspection high-water mark was identical in every sample, but may be dominated by inherited pre-exec runner memory, so this measurement cannot establish that the workload's own peak memory was unchanged.

This caveat does not invalidate the much larger, tightly clustered self-compilation RSS/GC-heap increase. It also does not prove that the library decrease is a general memory improvement. Avoid comparing native and hosted FFI RSS as compiler-memory figures.

The kernel mechanism was checked against primary source, without running a new measurement: [Linux fork address-space setup](https://github.com/torvalds/linux/blob/master/kernel/fork.c) (`dup_mm` sets the copied address space's high-water RSS) and [Linux exec accounting](https://github.com/torvalds/linux/blob/master/fs/exec.c) (`setmax_mm_hiwater_rss` retains the previous address space's peak). The exact fork/vfork execution path was not traced here, so attributing these particular constant values to that floor remains an inference.

## Timing interpretation

The draft's five paired wall-ratio medians and ranges match the records. The self-compilation headline, 1.0020, hides substantial order sensitivity: both pairs where the new compiler runs first are slower; two of the three pairs where it runs second are faster. Runtime and FFI also have differences in both directions. The native FFI window is only 6–9 ms, including launcher/startup/output overhead, and even user/system CPU components sometimes round to zero. Do not infer a 14.6% compiler regression from that workload's paired median.

The library inspector's 0.9753 median paired ratio and 1.0146 ratio of separate medians have opposite signs, as the draft correctly discloses. The FFI inspector's 0.5559 minimum ratio comes from one full-run outlier (0.418 s versus approximately 0.237 s for the other full samples); the corresponding internal compilation elapsed time remains approximately 0.021 s. That extreme does not establish a 44% lowering saving.

The inspected library snapshot is **67,793,315 bytes**, compared with **2,140,940 bytes** of full-mode LLVM output. Both variants perform snapshot construction, guard evidence collection, JSON serialization and publication. The worker sets `elapsed_seconds` before `observer.save()`, so it excludes final snapshot serialization and artifact publication. The median difference between outer wall time and that inner measurement is approximately 1.64 s for full and 1.91 s for finalized inspection. That difference also includes process startup and other surrounding work; it is not a separately measured serialization duration. Say that snapshot/publication overhead is substantial and shared, not that a measured percentage of total time is proven to be serialization. The CLI experiment cannot isolate the cost of lowering.

Skipping lower is established by stage records, absence of LLVM artifacts, and identical finalized snapshot bytes. It avoids the recorded LLVM output, but this experiment does not show a general end-to-end speedup. Snapshot/guard-evidence processing is a reasonable future profiling target if inspection cost becomes a priority; no additional optimization is required to make the current claims accurate.

## Method and completeness

The controlled aspects are sound for advisory measurements: one common absolute input/root, exact output checks, sequential CPU affinity (all recorded child affinities are CPU 0), alternating order, warmups retained/excluded, and unchanged source/binary/runner identities. Five pairs on a shared host, without instruction counts or isolated-host replication, are insufficient to infer equivalence or a small timing effect. No cost claim here should extend to LLVM machine-code generation, application execution, all compiler workloads, or whole-process-tree memory.

The all-mode report is correctly marked failed overall: its three native workloads completed, then the first library-inspection warmup exceeded the five-second resource guard at 5.673867 s. The completed inspection-only report uses an explicitly revised ten-second guard; it has the same measurement-runner hash and source tree. The README clearly preserves this failure and describes the rerun. There is no recorded evidence of discarded native samples or selective native reruns. Keep workload completion distinct from overall report completion.

