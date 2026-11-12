# Float AOT acceptance comparison for #1300

The predeclared median criterion passed in one fixed set of 15 alternating pairs on CPU 3: baseline **42.484454 ms**, RC1 **42.134673 ms**, ratio **0.99176685**. RC1 is 0.823% faster by this metric and within the issue's 5% limit. All 30 measurements and four warmups are retained; none was discarded and no additional sampling was performed.

## Exact inputs and method

The historical source is `0ec827ac34837cc917627e1ce594c484db6e9227`, tree `165fadd2f153404ce2619dee5b0983ae223e7ed8`, independently confirmed as the first parent of #1268's merge `b40ee875bf72b86804c4f5a300066f4f7c3eb20b`. The RC1 build uses local commit `7c75948747090c7d6a0a0bf76f9aecee8de90a15`, complete tree `64f1fb7295efd25401052d61a22823681e5669ab`. GitHub's commit API confirms that the remote candidate `886ed9153e954b387f2afd39578a21168771ae6e` and merged main `30822255ee7ee704e0e780e01cd8c23357ba13ab` have this identical tree. The local checkout identity is recorded separately from the remote commits.

Both clean source checkouts contain the byte-identical original `bench/pyperformance/float.py`: 1,958 bytes, SHA-256 `cc19566e50f47bc26d78324475260ff9808509266b70fffeff0091d1144388d0`. Each run uses argument `10`, with the original default of 100,000 points per loop. Each source's hosted compiler emits its own AOT program with pinned CPython 3.13.16 and LLVM 19.1.7, default optimization passes and AOT level 2, isolated caches, and retained raw IR. No compiler bootstrap was needed for this hosted-emission comparison.

Two warmup pairs precede 15 measured pairs. Order alternates old/RC1 then RC1/old. Every native invocation is pinned to CPU 3; all other session-owned native qualification workers had finished before the builds and measurement. The metric is the unmodified benchmark's internal loop-region `seconds` value. The complete printed result matches pinned CPython for both binaries and every sample. Toolchain executable versions/hashes, source identities, build commands/environment, binary hashes, raw stdout/stderr, timing/resource observations, symbols and complete disassembly are retained alongside this report.

## Retained variation and limits

RC1 sample 8 took **176.387793 ms**, including approximately **175.620 ms child CPU time** (132.248 ms user plus 43.372 ms system); the evidence does not justify attributing it merely to a scheduler pause. The baseline sample in that pair took 46.698006 ms. No cause is assigned. The all-sample means are **42.788819 ms** for baseline and **51.694442 ms** for RC1; their ranges are 40.492–46.698 ms and 39.651–176.388 ms, respectively. The median absolute deviations are 1.492 ms and 1.327 ms.

Before/after one-minute host load was 0.64/0.67. The process affinity allowed CPUs 0–8. LLVM reports host CPU `znver4`. Cgroup CPU counters, frequency and sibling-topology files were unavailable in this container and are recorded as null, so this receipt does not claim a fully controlled physical host or explain tail behavior. It establishes the stated median recovery on this pinned interleaved local comparison, not a broader performance guarantee.

Both native binaries have no `Point.__init__` symbol or disassembly reference. Baseline raw IR has one constructor call. RC1 retains the checked and copied loop calls, with the copied call marked `alwaysinline`. The source retains the deterministic `tests/ir/listguard_inline.py` / `.inline` fixture; its passing qualification is part of the already completed RC1 candidate full CI, separately from this performance measurement.

## All measured samples

| Pair | Baseline ms | RC1 ms |
| --- | ---: | ---: |
| 1 | 43.349974 | 43.125131 |
| 2 | 41.476186 | 41.796820 |
| 3 | 40.578795 | 40.097960 |
| 4 | 40.992495 | 41.764272 |
| 5 | 41.488033 | 39.651413 |
| 6 | 40.976712 | 40.903968 |
| 7 | 44.870840 | 39.828720 |
| 8 | 46.698006 | 176.387793 |
| 9 | 46.246692 | 42.134673 |
| 10 | 43.161730 | 49.248332 |
| 11 | 41.871457 | 43.056573 |
| 12 | 42.851006 | 51.200914 |
| 13 | 42.484454 | 42.341348 |
| 14 | 40.492000 | 40.416781 |
| 15 | 44.293905 | 43.461935 |
