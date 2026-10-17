# Rolling compatibility findings

This log tracks changes after the [2026-10-17 audit](compatibility-2026-10-17.md).
Keep the original measurements as a historical baseline. Append new measurements
with the exact main SHA, merged PRs, commands, inputs and observed outcomes.
Do not replace a result merely because a PR description predicts an improvement.

**Latest evaluated main:** `d3fbfc6f5f6d5650f25ffc0d97be93b512f41a6f`.
**Baseline audit PR:** [#635](https://github.com/den-run-ai/pystachy/pull/635).

## Checkpoints

| Check | Main / changes since baseline | Findings |
|---|---|---|
| 2026-10-17 initial audit | `d3fbfc6f`; includes #598, #599 and #603 | 141/476 import programs compile; 46 upstream files excluded by overlay. 501 selected stdlib checks and 62 port checks pass; all 18 adapted benchmark programs match. Detailed evidence is linked from the baseline. |
| 2026-10-17 follow-up | Same `d3fbfc6f`; no additional merges | Existing results still describe current main. No unchanged full suites were rerun. #600–#602, #604–#609, #622–#624, #629–#634, #583 and #170 remain open at this checkpoint; proposed support is not counted as shipped. |

## Checks to run when the pending work lands

These are impact targets, not assertions that the PR will make the whole module
or package work. Combine consecutive relevant merges into one measured revision
when practical, preserving attribution and the previous result.

| Pending work | Focused remeasurement |
|---|---|
| #600 import rebinding, #601 namedtuple | Stdlib import sweep with identical CPython inventory; `unittest` and unmodified fnmatch harness probes; inspect/socket-related first errors. Record subsequent blockers instead of declaring the harness supported. |
| #602 `sys.warnoptions` | Warnings-dependent imports and package probes. Preserve whether a probe uses the stdlib overlay or only package/dependency roots. |
| #606 TextIOWrapper, #608 token | Tokenize/inspect/doctest import and selected API probes; distinguish remaining module-level `del` (#612) from completed io/token support. |
| #607 Any signatures and #629–#631 variable/constructor/iterator inference | Exact upstream and minimal-adaptation package probes, especially tomli-w/ordered-set/pyfiglet/iniconfig; retained port workloads; Any metadata and iterator contracts. Cache signature inference (#620) remains a separate question. |
| #632 item mutation templates, #633 generator channels, #634 recursive diagnostics | Mutation and generator-channel tests; iniconfig iterator probe; forwarding recursion (#595) versus improved diagnostics. Do not treat an improved diagnostic as acceptance. |
| #604 replace, #605 owned-string capacity trim | Bounded/unbounded replacement correctness, selected port text workloads and memory probes. Separate capacity/peak-memory results from throughput; retain input sizes and GC settings. |
| #623 shared short strings, #624 regex subject retention | Regex tests, split/subject-retention probes and selected regex timings; distinguish allocation/cache lifetime changes from matcher speed. |
| #622 imported decorator names | Decorated imported-function diagnostics and affected API probes. Record diagnostic improvements separately from compatibility gains. |
| #583 ndarray, #609 FFI buffers, #170 CPython embedding | Example/FFI checks and explicit interop calls. Classify standalone compiled arrays and embedded CPython separately from native NumPy/PyPI compatibility. |
| Other compiler/runtime/library/port/test-tool merges | Read the actual changed files and run the matching retained probes. Documentation-only merges do not require another compiler build or unchanged sweep. |

## Recording rules

- Verify the event's PR is merged into the main history and read current main;
  overlapping events may refer to the same already-evaluated source state.
- Compare file changes before choosing tests. Rebuild the compiler when its
  sources/runtime change; retain compiler-file hash, source SHA and toolchain.
- Use `tools/import_sweep.py --metadata` when repeating imports. Keep the same
  CPython version, module inventory and overlay, or explain the denominator change.
- Keep import IR, executed JIT/AOT APIs, adapted programs, upstream tests hosted
  by CPython, and actual compiled upstream suites as separate evidence categories.
- Add compact result deltas and links to normalized evidence. Include failures,
  timeouts, newly exposed blockers and regressions; retain exact reproduction
  commands and relevant existing issue owners. Single noisy timing samples are
  not regression measurements.
- Update the open audit PR with findings. After it merges, use a small follow-up
  PR for material changes. Do not edit another session's implementation branch or
  merge its PR as part of the audit. Read its current coordination notes first
  when a finding overlaps active work.
- If no relevant source or measured outcome changed, avoid another commit or
  repeated no-change comment. Keep the latest *evaluated* SHA distinct from a
  newer revision whose evaluation is blocked or incomplete.
