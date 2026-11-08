# Worker ownership blockers

Do not merge this research branch. It preserves an unqualified local-worker extraction and the failures that stopped its promotion.

A worker can fork an in-group descendant after cleanup takes its last process snapshot; the final per-PID kill misses that child. The probe's surviving child wrote a proof file after scope exit. Separately, a successful leader can leave an active child behind, release its whole-tree resource reservation, and allow the next job to start even with one worker and one reserved CPU.

The recorded probes ran under CPython 3.12.14 on Linux. The original scenario bodies are preserved in the script below, with owned-group fallback cleanup. The combined saved script was syntax-checked but was not rerun after the major-blocker stop.

```sh
python research/worker-ownership/worker_ownership_repro.py tools
```

[Observed results and source hashes](worker_ownership_results.json) identify the tested local checkpoint and its identical published tree. [Source comparison](worker_ownership_comparison.txt) confirms that the failing mechanisms are inherited from [PR #1133 at 4d788103](https://github.com/den-run-ai/pystachy/pull/1133); no additional probe was run on that original revision.

The v0.3.1 release tree and PR #1150 are outside these findings. All test process groups were cleaned up. No new qualification runs were started after the stop.
