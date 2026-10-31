# Recursion guard tail-sharing follow-up

Status: validation and measurements in progress; performance acceptance remains open.

The reviewed implementation is PR #996 head `aaec00cc81a862a2b29c117003e7c9cc73e1a3c1`, tree `2dd336a2a8f71d9a2c36d1fd233af24fee81c2a1`, based on main `06e3ad5d08514ba31fb231fe4636a962fe6578e3`. This evidence branch preserves checkpoints without changing the reviewed PR source.

## Implemented changes

The initial region optimization removes repeated entry checks and bookkeeping only inside a bounded private graph selected by a non-raising remaining-depth test. Insufficient depth executes the original guarded body. The file eligibility proof permits immediately rooted scoped files; unmanaged files, weakrefs, exit hooks and embedding boundaries remain conservative.

The latest change shares equivalent private partial-region return tails before mandatory inlining. It requires the same slot load, direct private child call, return, types and external operands, permits alpha-renaming only of the two local results, and excludes special control-flow/metadata uses. It preserves both the guarded fallback and the original proof/budget. It adds 89 source lines; total compiler/runtime growth relative to 993fb17e is 782 net lines.

A separate smoke-harness fix checkpoints completed measurements atomically, preserves incomplete/error states and uses the repository's existing 15-minute job ceiling. Workloads, sample counts, warning criteria and per-command timeouts are unchanged.

## Fresh recovery and provenance

A scratch-workspace cleanup removed local tools and uncommitted diagnostic files after an earlier successful bootstrap. Source commits, existing benchmark datasets, and CI artifacts survived. The exact 85,660-byte startup diagnostic export was lost; a later report must distinguish partial transcript recovery from a complete raw dataset. Existing AMD EPYC 9V74 results remain historical.

The restored local environment uses Intel Xeon Platinum 8573C, CPython 3.13.16, LLVM/Clang 18.1.3, and Valgrind 3.22.0. The toolchain manifest records exact distributions and hashes; binary identity with the old toolchain is not asserted. New comparisons rebuild all participating variants on this host.

## Completed checkpoint

A fresh local bootstrap completed successfully in 334.3203 seconds with an unchanged 137-file source snapshot. All three native binaries are byte-identical (SHA256 `066ca28a41256c32bb4962b6dfd82a4a8ce883e963ce4557a4be6aca9ad935e3`). All three compiler IR modules are identical: 805,028 lines, SHA256 `f918a33a73bb3f8164b986089534fa1370c91272649017db54a41527a4f56409`. All three runtime modules are identical: 18,805 lines, SHA256 `940a694da5ea93214d1308a8eb635b47d8d0a9d4256c63d084c24f5099f8aa5f`, also matching the prior runtime IR.

Current-head CI performance smoke completed successfully with all 11 workloads, a complete schema-2 JSON report, and no warning-triggering metrics. Its AMD EPYC 7763 runner observed whole-JIT-process overhead of 19.31% for fnmatch and 19.46% for mixed JSON versus main; corresponding JIT kernel changes were 2.45% and 4.97%. Neither case triggered confirmation because the initial process ratio was below 20%. An advisory pass is not performance acceptance.

- [CI smoke run](https://github.com/den-run-ai/pystachy/actions/runs/41214277702)
- [Verified complete artifact](https://github.com/den-run-ai/pystachy/actions/runs/41214277702/artifacts/13047717899), ZIP SHA256 `59f096079b53c0ca9184988c83ea80208ca165f349cfb08b1c571aabe845a222`.
- JSON SHA256 `936d3705f5847c98cf59cb0978c3fa04576d9dface9d5d51464a8e2e8cdb477d`.

Fresh local startup/kernel/count/compilation measurements, focused native fixtures and a complete 3,918-case compilation comparison are still pending. The full current-head correctness workflow is also pending at this checkpoint. PR #996 remains draft and unmerged.
