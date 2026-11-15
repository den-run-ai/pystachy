# Retained parity prepared for the compiler-stage follow-up

Preparation only: the comparator has **not** been run by the preparing agent. Run it only after the active full verification and other heavy jobs finish.

The direct comparison is the retained #1499 native binary against the new native binary, both consuming the current frozen source and identical library/runtime inputs through the same `PYSTACHY_HOME`. `preflight-identity.json` records the clean published candidate `eabfe7b3d8f1be3e4615442423c7d3fbab10285b`, compiler hashes, all 4,579 ordered input paths/hashes, 105 library/runtime input records, 61 compiler source files, and 9,045 actual fixture/dependency files. It also records identity against the original main-reference library/runtime inputs. This is a preflight snapshot, not parity execution evidence.

Execute in the foreground using the yielding execution tool:

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python /workspace/scratch/9f30aa4fd4fd/evidence/irsame/run_parity.py
```

The wrapper records `before.json`, `after.json`, `command.json`, `run.log`, and `run.status`. It refuses a dirty candidate checkout, a corpus other than 4,579 paths, or unequal reference/candidate library inputs. It runs the preserved comparator with two workers, a clean environment, default optimizations, IRCHECK unset, and evidence-local TMPDIR. It never builds either compiler.

The comparator retains per-case messages, exit statuses and comparator reports; changed LLVM remains on disk. `harness-copy.json` records that its only changes from the previous retained harness are the two output/source path-prefix substitutions. Its underlying maintained comparator remains byte-identical to current `tools/irsame.sh`.

The wrapper then calls `summarize.py`, which writes `case-results.json` and `summary.json`. A passing summary requires exactly 4,579 complete results, matching normal exit statuses, byte-identical raw diagnostics, empty comparator reports, no new rejections, identical runtime/library inputs, and unchanged binaries/source/fixtures during the run. It records actual accepted/rejected counts; the historical expectation was 2,653/1,926.

To regenerate only the summary after reviewing retained artifacts:

```sh
/workspace/scratch/c2b093657c17/dev-venv/bin/python /workspace/scratch/9f30aa4fd4fd/evidence/irsame/summarize.py
```

The run wrapper refuses to overwrite existing execution evidence. Archive the directory before reusing it. Missing/incomplete evidence is a failed or incomplete run, never a pass.
