# Examples

These small applications exercise the compiler, standard-library ports, numerical
code and packaging. Most run unchanged under CPython, Pystachy JIT and Pystachy
AOT. Each guide gives commands and describes its supported behavior.

Start with the [installation guide](../docs/install.md). Commands in an individual
guide run from that example's directory unless it says to use the repository root.
The extra requirements below are in addition to the compiler and its build toolchain.

| Example | Purpose | Maintained checks | Extra requirements |
|---|---|---|---|
| [agent](agent/README.md) | Typed tool loop, JSON messages and recorded repair | [App corpus](../tests/programs/apps/example_agent.py); HTTP smoke in its guide | Linux and GNU coreutils; `curl` and a model server for live HTTP |
| [column](column/README.md) | Table alignment with `io.StringIO` | [App corpus](../tests/programs/apps/example_column.py) | None |
| [csvstat](csvstat/README.md) | CSV parsing, reports and numeric statistics | [App corpus](../tests/programs/apps/example_csvstat.py) | None |
| [cut](cut/README.md) | Field and character selection with `getopt` | [App corpus](../tests/programs/apps/example_cut.py) | None |
| [json_repair](json_repair/README.md) | CPython companion for the native JSON-repair port | [Extension replay](../tests/upstream/json_repair/extension.py) in the FFI suite | Linux and GIL-enabled CPython 3.12+ for the companion |
| [latency](latency/README.md) | Access-log statistics with `statistics` | [App corpus](../tests/programs/apps/example_latency.py) | None |
| [linediff](linediff/README.md) | Unified and word diffs with `difflib` | [App corpus](../tests/programs/apps/example_linediff.py) | None |
| [mailmerge](mailmerge/README.md) | Message rendering with `string.Template` | [App corpus](../tests/programs/apps/example_mailmerge.py) | None |
| [mazepath](mazepath/README.md) | Breadth-first search with `collections.deque` | [App corpus](../tests/programs/apps/example_mazepath.py) | None |
| [montecarlo](montecarlo/README.md) | Seeded sampling with `random` | [App corpus](../tests/programs/apps/example_montecarlo.py) | None |
| [nanogpt](nanogpt/README.md) | CPU float64 inference and analytic training | [Inference](../tests/programs/apps/example_nanogpt.py) and [training](../tests/programs/apps/example_nanogpt_training.py) in the app corpus; BLAS parity | PyTorch for offline export/upstream checks; optional LP64 BLAS at runtime |
| [ndarray](ndarray/README.md) | Float64 arrays, views, broadcasting and fused expressions | [App corpus](../tests/programs/apps/example_ndarray.py), [edges](../tests/programs/apps/example_ndarray_edges.py), [elementwise](../tests/programs/apps/example_ndarray_elementwise.py) and [upstream cases](../tests/programs/apps/example_ndarray_upstream.py); BLAS checks | NumPy for reference checks; optional LP64 BLAS at runtime |
| [package](package/README.md) | Build and consume a source wheel with a port dependency | [Package smoke](../tools/package_smoke.py) in packaging and distribution CI | `uv`; see [packaging requirements](../tools/requirements-packaging.txt) |
| [route](route/README.md) | Pattern matching and cached event classifications | [App corpus](../tests/programs/apps/example_route.py) and [empty traces](../tests/programs/apps/example_route_empty.py) | None |
| [suggest](suggest/README.md) | Spelling suggestions with `difflib` | [App corpus](../tests/programs/apps/example_suggest.py) | None |
| [topk](topk/README.md) | Word counts and heap-based selection | [App corpus](../tests/programs/apps/example_topk.py) | None |
| [urlstats](urlstats/README.md) | URL parsing and canonicalization with `urllib.parse` | [App corpus](../tests/programs/apps/example_urlstats.py) | None |

## Checks

The app corpus compares JIT and AOT execution with recorded CPython output and
exit status. From the repository root, run all example fixtures with:

```sh
make test FILES="tests/programs/apps/example_*.py"
```

These fixtures cover representative behavior and errors. The individual guides
also document HTTP smoke, NumPy and upstream PyTorch comparisons, and their
requirements. The JSON-repair extension replay runs under `make test-ffi` when
the pinned GIL-enabled CPython is available. Package installation has its own
`python3 tools/package_smoke.py` check. `make blas-check` covers the optional
ndarray and nanoGPT adapters; CI runs it with reference BLAS and OpenBLAS.
See [testing](../docs/testing.md) for the full verification groups.

## Benchmarks

The `bench.py` scripts are CPython drivers that build and run the examples;
they are separate from the applications being compiled. Each guide names its
workload and command. Generated inputs and executables go to `build/<example>/`.
The numerical examples also keep recorded results beside their workloads.

Check output agreement before interpreting timings. For a regression comparison,
use the same source, input, toolchain, CPU and thread settings, alternate the
builds being compared, and report repeated runs. Separate compilation, process
startup and warm operation timings. Record compiler revisions with new results;
older tables linked from the guides describe only their recorded builds and hosts.
The [performance guide](../docs/performance.md) covers timing and memory measurement.
