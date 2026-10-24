# Core library and benchmark expansion, 22 October 2026

The sweep found useful coverage to add without changing compiler or runtime behavior:
heterogeneous JSON and containers, generator workloads, and `difflib.context_diff()`.
The latter needs one localized library adaptation: spell its fixed prefix table as a
dictionary literal, preserving order, instead of unsupported `dict()` keyword arguments.
The upstream diff algorithm is unchanged.

Baseline: main `5f7ec7619867accfef5bc30cf7bffa6328967ac6`, CPython 3.13.16,
LLVM 18.1.3, Linux x86-64. The native compiler's three-stage fixed points were
672,328 compiler IR lines and 18,709 runtime IR lines. Compiler/runtime source
was unchanged by these additions. The test and library sources are those in this
change; baseline failures below were observed before the literal-table adaptation.
This selected sweep does **not** advance the broad compatibility audit checkpoint.

## Scope and delivered coverage

Core collection, parsing, configuration, text, I/O and numeric consumers were selected.
The 55-name import set is reproduced below. It includes shipped modules, compiler builtins,
and useful pure-Python candidates from CPython. Imports use the existing overlay policy:
exclude top-level names supplied by Pystachy's `lib/` so upstream files do not hide them.
No missing-module stubs were supplied. Compilation of imports is distinct from executing APIs.

Excluded from the selection: CPython bytecode/import/runtime internals (`opcode`, `_imp`,
`_ast`, `dis`, interpreter inspection), GUI/terminal applications, networking clients and
servers, database drivers, asynchronous/thread/process frameworks, packaging/installers,
platform-specific services and third-party extension frameworks. Compression and hashing
were sampled only as dependency boundaries (`gzip`, `hashlib`); this change adds no native
C-extension replacements. `gettext` catalogs remain outside this expansion absent the
CLI consumer required by the library scope. Integer overflow, arbitrary-precision arithmetic,
unsupported binary-file APIs and reflection are not waived to make tests pass.

| Area | Delivered check | Boundary |
|---|---|---|
| pyperformance 1.14.0 | Four additional adapted programs: `generators`, `comprehensions`, `json_dumps`, `json_loads`; maintained suite expands from 18 to 22 | See [port notes](../../bench/pyperformance/README.md) for source pins and adaptations. These are correctness-checked programs, not official pyperformance scores. |
| CPython JSON | Selected decode, dynamic encode and recursive/default/circular-value cases | [Core-sweep guide](../../tests/upstream/core-sweep.md) identifies exact methods, source hashes, omissions and recording commands. |
| CPython containers | Dynamic dict values and heterogeneous deque scenarios | Tests preserve mutation and observable values; they do not establish complete dynamic protocol coverage. |
| CPython difflib | Context-diff halves of two `TestOutputFormat` methods, all five range-format assertions, and 11 public-API scenarios | Empty/identical inputs, insertion/deletion/replacement, context grouping, filenames/dates, Unicode and missing final newlines. No `diff_bytes`, `ndiff` or `HtmlDiff` support is claimed. |

The 22-program benchmark smoke run matched CPython in JIT and AOT. The five JSON/container
programs passed 10 native checks, 10 per-allocation-GC checks, and 10 checks with the
CPython-hosted compiler. The additional context-diff program passed native JIT/AOT,
normally and with per-allocation GC: **4/4 executions**. Its original, unmodified
`TestOutputFormat` class separately passed **4/4 hosted unittest methods** against the
adapted library, and the adapted library passed **75/75 doctest examples**. These hosted
checks are not compiled execution of CPython's entire `test_difflib` suite. Full merge
verification is reported in the PR, separately from these focused results.

All six maintained differential programs are listed in the core-sweep guide. They run
through the normal corpus harness, including CI's configuration variants. Recordings come
from the pinned CPython, not Pystachy's output. No performance improvement is inferred from
correctness smoke runs; current benchmark timing claims remain separate in
[pyperformance results](../pyperformance.md).

## Selected import census: 43 of 55 compile to IR

This denominator is deliberately smaller than the historical broad stdlib sweep and
includes shipped modules. It must not be compared to the older 470+ source-module
counts as a coverage percentage or an improvement. Of these 55 isolated import programs,
**43 compiled, 12 were rejected, none timed out**. No imported function was exercised
by this census.

| Rejected import(s) | First observed blocker | Existing follow-up |
|---|---|---|
| `calendar` | `locale.localeconv` redefinition | [Stdlib scope, #257](https://github.com/den-run-ai/pystachy/issues/257) |
| `configparser` | `collections.ChainMap` missing | [Stdlib hubs, #11](https://github.com/den-run-ai/pystachy/issues/11) |
| `copy` | `copyreg` dispatch dictionary uses callable/type keys | [Type-keyed dispatch, #805](https://github.com/den-run-ai/pystachy/issues/805) |
| `decimal`, `fractions`, `statistics` | Overlay imports eventually require `_contextvars` | [C-module gaps, #491](https://github.com/den-run-ai/pystachy/issues/491) |
| `enum` | Unsupported `FlagBoundary` base class | [Class/hierarchy scope, #7](https://github.com/den-run-ai/pystachy/issues/7) |
| `gzip` | Missing `zlib` | #491; extension-backed compression not added here |
| `hashlib` | Import graph reaches `_thread.RLock` used as a class value | #491/#7; import rejection alone says nothing about a native hashing implementation |
| `ipaddress` | `functools.total_ordering` unsupported | #11/#7 |
| `pathlib` | Import graph reaches unsupported `os.O_RDONLY` | #11 |
| `pprint` | Executable class-body dictionary assignment | #7/#805 |

`statistics` is a useful overlay caveat: its shipped port works without these upstream
optional dependencies, and `statistics.fmean([1.0, 2.0, 3.0])` compiled with the normal
shipped search path. Adding CPython's `decimal`/`fractions` makes imports reach their
unsupported dependencies. The census result is therefore an overlay configuration
result, not a regression of the supported `statistics` API.

## Functional re-probes and remaining work

Fifteen small API compilation probes were also tried, independently of the import census.
With explicit generic constructor arguments, five compiled on baseline: `deque[Any]`,
`defaultdict[str, Any]`, `OrderedDict[str, Any]`, `Counter[Any]`, and `statistics.fmean`.
The other ten probes were rejected; they include both ordinary and entry-module
`dynamic-any` versions of `graphlib` and `heapq.merge`. An entry-module pragma does not
change the storage policy of imported modules.

| Consumer | Baseline observation | Decision |
|---|---|---|
| `difflib.context_diff()` | Fixed prefix table used unsupported `dict(insert=..., ...)` | Delivered equivalent literal table and differential tests. |
| `difflib.ndiff()` / `Differ.compare()` | Recursive `_fancy_helper` yield type cannot be inferred | Remains under #257; no annotation-only success is assumed. |
| `difflib.HtmlDiff` | Class attribute `_file_template` type not inferred | Remains under #257. |
| `heapq.merge([1, 3], [2, 4])` | Cannot infer local empty list `h` | Remains under #257; same failure with only the caller opting into dynamic Any. |
| `graphlib.TopologicalSorter(...).static_order()` | Cannot infer field `_node2info` | Imports compile, API still fails; #257. Same failure with caller-only dynamic Any. |
| `argparse.ArgumentParser().parse_args(...)` | Multiple inheritance in `ArgumentParser` | Imports compile, selected CLI consumer still fails; #7/#11. |
| `base64.b64decode(...)` | `_bytes_from_decode_data` tests a bytes-like type tuple unsupported by `isinstance` | Import compilation does not establish decode support; #491. |
| `statistics.mean([1, 2, 3])` | Cannot infer `_sum`'s empty set of types | Existing [#746](https://github.com/den-run-ai/pystachy/issues/746); `fmean` is a different API. |
| Empty `defaultdict` / `OrderedDict` with Any values | Context-only constructor type binding fails; explicit `defaultdict[str, Any](factory)` / `OrderedDict[str, Any]()` compiles | Use explicit type arguments in scoped tests; do not claim the contextual inference gap is fixed (#616/#777). |

The successful collection probes establish compilation only; the maintained deque and
JSON/dict programs establish their own native behavior. They do not establish full
Counter/OrderedDict/defaultdict parity. Dynamic Any remains experimental; this expansion
does not satisfy all of [#802](https://github.com/den-run-ai/pystachy/issues/802),
[#108](https://github.com/den-run-ai/pystachy/issues/108) or the retained-memory acceptance
work in [#202](https://github.com/den-run-ai/pystachy/issues/202). Benchmark acceptance and
coverage remain related to [#361](https://github.com/den-run-ai/pystachy/issues/361).

## Reproduction and provenance

The selected imports can be repeated from the repository root with pinned CPython.
This uses the same maintained overlay and import-compiler helpers as the broad sweep;
no throw-only module stubs or copied implementations are introduced:

```sh
python3.13 - <<'PY'
import os
from pathlib import Path
import sys
import sysconfig
import tempfile
from tools.import_sweep import compile_one, overlay, ported

root = Path.cwd()
selected = '''abc argparse base64 binascii bisect calendar codecs collections
collections.abc colorsys configparser contextlib copy csv dataclasses datetime decimal
difflib enum fnmatch fractions functools genericpath getopt graphlib gzip hashlib heapq
html html.parser io ipaddress itertools json keyword math operator pathlib posixpath
pprint random re shlex statistics string struct textwrap time tomllib types typing
unicodedata urllib.parse warnings weakref'''.split()
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp)
    overlay(sysconfig.get_path('stdlib'), ported(str(root / 'pystachy')), str(path / 'overlay'))
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYSTACHY_')}
    env.update(PYSTACHY_HOME=str(root), PYSTACHY_PATH=str(path / 'overlay'))
    results = {}
    for name in selected:
        job = path / name
        job.mkdir()
        result, _ = compile_one([sys.executable, str(root / 'pystachy.py')],
                                env, str(job), name, 90, [])
        results[name] = result
        print(name, result)
    print('selected', len(results), 'compiled', sum(v == 'OK' for v in results.values()))
PY
```

The installed CPython 3.13.16 pure-Python stdlib input tree contained 633 `.py` files,
excluding `site-packages` and `__pycache__`. Its manifest digest was
`97c231869ad36230b0f3ee5e08bc1fa883dc1c782e87840d034cee133e0283f4`:
sort relative POSIX paths, append `path + NUL + SHA256(file) + newline` per file,
then SHA-256 that byte string. Pystachy's compiler and shipped library inputs are pinned
by the baseline commit above. This fingerprint identifies the selected installation;
a different platform's stdlib tree can differ without implying a compiler regression.

CPython-derived test sources use commit
`cbc944f4bc59639a444dd971c737788ba2283a91`; exact files and hashes are in the
[core-sweep guide](../../tests/upstream/core-sweep.md). `test_difflib.py` has SHA-256
`dc6b140c8dd31e6971888070ea5175a0ab72ecadbdc96956071ceb062f34e636`.
The existing PSF license and synchronized third-party notices cover the adaptation.
The upstream `difflib.py` source and hash remain in [library provenance](../../lib/provenance.md).

Run the context-diff regression on a built checkout with the matching LLVM tools:

```sh
PYTHON=python3.13 tests/record.sh upstream_difflib_context
PYSTACHY_JOBS=1 tests/run.sh ./pystachy 'jit aot' tests/programs/upstream/upstream_difflib_context.py
PYSTACHY_JOBS=1 PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' tests/programs/upstream/upstream_difflib_context.py
```

The ordinary recording must remain unchanged by the native executions. Restoring the
baseline prefix construction makes the new context-diff program fail to compile at
`dict()`'s `insert` keyword. The original CPython tests can be run against the adapted
module in a CPython source checkout; the focused hosted check selects the unchanged
`TestOutputFormat` class and runs `doctest.testmod()` on `lib/difflib.py`.
