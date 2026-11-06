# Compatible receiver annotations

The receiver overlay now works under **both native Pystachy and mypyc 2.4.0**.
This changes research host preparation, without changing the compiler algorithms
or production source. [Raw evidence](results/receiver-compatible.json),
[complete overlay](results/receiver-compatible-overlay.diff), and
[receiver counts](results/receiver-compatible-counts.json) accompany the runner.
This experiment uses the `30ea5f7` snapshot, whose compiler sources are unchanged
from #1090, with Clang 18.1.3 O2 for mypyc C compilation and CPU 8 for frontend
timings. Later frozen-source and final-tree checks are reported separately in
[OPTIMIZATIONS.md](OPTIMIZATIONS.md).

## Binding the same source for both hosts

The overlay annotates 1,189 helper receivers in 27 modules. Mypy sees the concrete
class; ordinary execution and Pystachy receive the runtime alias:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.pystachy_compiler.gen import Gen
from typing import Any as Gen  # type: ignore[assignment]
```

The deliberate assignment override preserves Pystachy's existing call-site
specialization. A missing-field negative control confirms that mypy still sees
the concrete receiver; a compiled circular-import probe uses direct native field
access. Three `TYPE_CHECKING`-only non-None assertions replace the previous casts
and preserve the established narrowing invariants without executing the
assertions at runtime. Ordinary CPython still evaluates the `TYPE_CHECKING` guards.

The spellings matter. Putting the fallback in `else` passed native rebuilding but
made mypyc emit an allegedly-unreachable-code trap during import. Putting it
before the class import erased concrete receiver typing. The original casts also
failed native acceptance. These superseded attempts are recorded separately.

## Validation and timing

Two fresh native generations, temporary O0 then final O2, reproduced the frozen
ordinary compiler, overlay compiler, and runtime IR: six generated-compiler
comparisons plus two retained build-IR comparisons. Source identities stayed
unchanged. Native and mypyc preparation produced exactly the same overlay.

Five interleaved fresh processes per host and workload, pinned to CPU 8, produced
**40/40 matching IR outputs**. Both mypyc hosts loaded all 48 compiler modules as
extensions. The four fresh oracle hashes also equal the previous CPython oracle
hashes on these unchanged inputs; CPython was not rerun here.

| Frontend workload | Previous typed mypyc | Compatible typed mypyc |
|---|---:|---:|
| Frozen compiler source | 7.403 s | 7.149 s |
| Runtime source | 0.131 s | 0.132 s |
| JSON repair | 0.420 s | 0.436 s |
| NameGenerator | 0.044 s | 0.043 s |

Self-frontend ranges overlap: 7.087–7.545 s versus 6.863–7.199 s. These results
retain the typed-host performance; they do not establish a general extra speedup.
Median peak RSS was 644.6 versus 644.7 MiB. Preparation is excluded: the new host
took 22.19 s to generate C and 61.17 s to compile/link it, each observed once.

## Reproduce and limits

Use the pinned source/tool identities and exact commands in the raw report.
`receiver_compatibility.py --generations 2` prepares the overlay and requires all
native witnesses. With LLVM 18's tools on PATH, run
`CC=clang python prepare.py --kind mypyc --receivers --jobs 4` and
`run.py --samples 5 --cpu 8`, using the report's frontend configuration with paths
adapted to the local checkout. Keep preparation and measured runs serialized.

The native receiver still uses `Any` specialization. This is not general support
for classes imported only under `TYPE_CHECKING`, nor for compiling complete
mypy/mypyc with Pystachy. The original receiver-only experiment did not rerun
full corpus validation, macOS, or other mypyc versions; final-tree corpus results
are reported separately in [OPTIMIZATIONS.md](OPTIMIZATIONS.md).
