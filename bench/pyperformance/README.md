# pyperformance benchmarks

These are 28 of the 52 benchmarks tried from [pyperformance](https://github.com/python/pyperformance)
1.14.0, adapted so that Pystachy compiles them. CPython runs the same adapted files, so each
comparison runs identical source in CPython, the JIT and AOT. The adaptations and smaller
inputs change the work, so these results are not comparable with published pyperformance numbers.
Use [Run](#run) for current measurements, [Adaptations](#adaptations) for workload changes,
[Census](#census) for dated upstream probes, and [Recorded results](#recorded-results) for
release comparisons.

## Run

From the repository root, after building the compiler:

```sh
make bench-pyperformance-check
make bench-pyperformance
python3 tools/bench_pyperformance.py --benchmarks richards nbody --runs 3
python3 bench/pyperformance/richards.py 10
./pystachy run bench/pyperformance/richards.py 10
```

Each benchmark's main takes the number of loops as its first argument; some also take input
sizes. It prints its results to standard output and the seconds of the part that pyperf would
time to standard error. The check runs small inputs once and compares CPython, JIT and AOT
output, without timings. `make bench-pyperformance` runs five processes per mode and writes
`build/pyperformance.json`. Both targets accept `BENCH_COMPILER`; `BENCH_ARGS` adds options to
the measured run. `--compiler "python3 -m pystachy"` uses the CPython-hosted compiler.
`PYSTACHY_*` settings apply to the compiled runs: `PYSTACHY_OPT=-all` disables the typed-IR
passes, and `PYSTACHY_GC_STRESS_PROGRAM=1` collects at every allocation in JIT and AOT runs, as
in `tests/run.sh`.

The separate [correctness controls](../../tests/programs/apps/pyperformance_controls.py)
exercise Fannkuch sizes 2–7, SOR with nonuniform inputs and sparse multiplication with
signed coefficients and an empty row. These run in the differential corpus. The SOR and
sparse timing workloads retain upstream's zero-filled inputs; their zero checksums alone
cannot validate the kernels.

## Shared pytest correctness suite

The [pytest tests](pytest/) import all 28 delivered benchmark modules and exercise
their existing workload functions with 50 ordinary pytest cases. The same files
run under original CPython pytest and the [native runner](../../docs/pytest-native.md):

```sh
PYTHONPATH=bench/pyperformance python3 -m pytest -q bench/pyperformance/pytest
python3 tools/pytest_native_suites.py --group pyperformance --mode jit
python3 tools/pytest_native_suites.py --group pyperformance --mode aot
```

The registry preserves all 50 cases in five independent categories, each with
its own original-pytest oracle. This bounds native build memory and separates
the JSON opt-in from typed workloads. `make bench-pyperformance-check` includes
both native modes in addition to its existing process/timing/provenance checks.

These original tests check full discrete results where available, finite numeric
reference values with explicit tolerances, complete generator order, nonuniform
SOR and signed sparse-matrix inputs, fixture cleanup, and JSON values. Reference
values were checked with pinned CPython 3.13.16. The JSON tests retain the workloads'
existing dynamic `Any` contract; the other tests use concrete types. They do not
require importing pyperf or changing any timed workload source.

Keep `bench-pyperformance-check`, the corpus controls and controller unit tests:
they also verify subprocess behavior, exact CLI output, timed regions, negative
controls and upstream provenance. Pytest results are correctness evidence, not
benchmark measurements. Use the timing controller above for comparable timings;
the native pytest invocation's compilation/startup cost is a separate measurement.

## Byte BPE

`bpe_tokeniser.py` provides the reusable `SimpleBytePairEncoding`, `bpe_train`,
`bpe_encode` and `BPE_PATTERN` API. The default benchmark uses the complete bundled
31,206-byte Frankenstein excerpt and vocabulary size 1,024. The existing suite's
`--smoke` run uses a tiny in-memory corpus and vocabulary size 260:

```sh
python3 tools/bench_pyperformance.py --benchmarks bpe_tokeniser --smoke
python3 bench/pyperformance/bpe_tokeniser.py 1 260 smoke
python3 bench/pyperformance/bpe_tokeniser.py 1 1024 bench/pyperformance/data/frankenstein_intro.txt
```

The CLI takes loops, then optional vocabulary size and corpus path. Run from the
repository root or pass an explicit corpus path. Its timer preserves upstream's
`train()` loop, including the `hello world` round-trip check and corpus encoding.
An independent untimed training pass prints every ordered rank, corpus token ID and
decoded byte for comparison across modes. Process wall time therefore includes this
correctness pass. Separate training, encoding and decoding measurements against
pristine upstream CPython are in the [byte-BPE showcase](../../examples/byte_bpe/README.md).
This educational tokenizer preserves its upstream splitting pattern and quadratic
encoder; it is not a throughput comparison with production Rust tiktoken.

## Provenance

The sources are `pyperformance/data-files/benchmarks/bm_NAME/run_benchmark.py` from the
pyperformance 1.14.0 sdist, `pyperformance-1.14.0.tar.gz`, SHA-256
`91f74393997b604375ad5b79bf569a24076d70181c076a53abad5383a238a8aa`. Given that sdist,
`python3 tools/bench_pyperformance.py --census pyperformance-1.14.0.tar.gz` checks these hashes,
checks that each changed hunk of a port carries a `# Pystachy port:` note and that each port
times what pyperf times, and compiles each upstream file with only pyperf's runner replaced,
reporting the first compiler error. An extracted `pyperformance/data-files/benchmarks`
directory is also accepted. In that mode each source hash is verified and the archive
hash is unmeasured (`null`).

The runner's [`UPSTREAM` map](../../tools/bench_pyperformance.py) is the authoritative
file-by-file SHA-256 manifest for all 52 sources. Its `BENCHMARKS` map selects the 28
ports and their normal and smoke inputs. Keep provenance in those checked manifests
when adding a port; the tables below describe adaptations and recorded first errors.

The 52 are the 31 benchmarks that this port set out to try, mostly CPU-bound and often cited,
and the 21 others that need no third-party package. The release's other 21 benchmarks list third-party
packages in their `requirements.txt` and are outside this runner's census: `asyncio_websockets`, `chameleon`,
`coverage`, `dask`, `django_template`, `docutils`, `dulwich_log`, `fastapi`, `genshi`,
`hg_startup`, `html5lib`, `mako`, `networkx`, `sphinx`, `sqlalchemy_declarative`,
`sqlalchemy_imperative`, `sqlglot_v2`, `sympy`, `tornado_http`, `xdsl` and `yaml`.
Their package dependencies need a separate assessment; exclusion from this census is not a
measured compiler rejection.

The byte-BPE corpus, [data/frankenstein_intro.txt](data/frankenstein_intro.txt), is
Mary Shelley's Frankenstein excerpt bundled with pyperformance 1.14.0 at commit
`2ab96f98f98274d07ebfdfd66e4f021723179706`. It is retained byte for byte: SHA-256
`6607193e67b7b459d082f5f2aea724e470615643d63ad2e205123b3076223da4`.
The [pristine byte-BPE source and provenance](../../examples/byte_bpe/upstream/provenance.json)
record the source, corpus and pyperformance license files used by the showcase.

## License

pyperformance is distributed under the MIT License; [LICENSE](LICENSE) and [AUTHORS](AUTHORS)
are its `COPYING` and `AUTHORS` files. Each port keeps its upstream header. `regex_v8.py`'s
header carries the V8 project's BSD license, and `raytrace.py`'s states the MIT License.
`deltablue` is excluded pending a separate provenance decision: its upstream docstring
says the JavaScript original was GPL-licensed. The other 28 benchmarks remain included.
`fannkuch.py`, `meteor_contest.py`, `nbody.py`, `pidigits.py`, `regex_dna.py` and `spectral_norm.py` say they
come from The Computer Language Benchmarks Game, whose programs are published under the
3-clause BSD License. `richards.py` and `richards_super.py` credit a Java version
"Copyright (C) 1995 Sun Microsystems, Inc.", and `chaos.py` says "Copyright (C) 2005 Carl
Friedrich Bolz". pyperformance distributes all of these files under its MIT License; their
origins are listed so that a license review can confirm that this suffices. See
[THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES). Byte BPE credits Shantanu Jain and
tiktoken; those notices also retain tiktoken's MIT copyright and permission text.

## Adaptations

Each edit is marked `# Pystachy port:` in the source. Some work around limits that later
compilers removed, such as those on generators, range values and slice assignment. They stay
because changing a port changes its timed work and checksums, which would then need new
measurements. The [census](#census) records what the upstream files needed at the
listed compiler revisions; rerun it to assess a newer tree. The runner
adaptations follow these rules:

- `import pyperf` is removed. A main that reads the loop count and sizes from `sys.argv`
  replaces `pyperf.Runner` and prints the results, or a checksum.
- The seconds the main prints are for the part that pyperf would time. Where the runner calls
  `bench_func()`, the main times a loop of calls of that function and nothing else; where it
  calls `bench_async_func()`, a loop that runs a coroutine of that function each time. Where it
  calls `bench_time_func()`, each benchmark function keeps its own timer around the same loop,
  with `time.perf_counter()`, which is `pyperf.perf_counter()`. Instead of returning the
  seconds, it appends them to a list `TIMED`, whose sum the main prints, and returns its result,
  or a checksum when it discards its result. `TIMED_PART` in `tools/bench_pyperformance.py`
  records which function each port times; the unit tests check the ports against it, and
  `--census` checks it against the upstream files.
- Older ports turn `range_it = range(loops)` into a list, from before range values were
  supported; later ports keep the range.

| Benchmark | Other adaptations |
|---|---|
| `async_generators` | The recursive `Tree.__aiter__()` async generator, its `async for` loops and the tree are unchanged. Where pyperf's `bench_async_func()` awaits the benchmark in an asyncio event loop, the main runs each coroutine with `send(None)`, as nothing in it suspends. A size argument limits smoke/GC runs to 100 nodes; the normal run keeps 100,000. The complete yielded sequence is checked outside the timer. |
| `async_tree` | The tree's classes, `gather()` and `TaskGroup` recursion and workloads are unchanged, with lib's `asyncio`. Its `__init__` and recursive coroutines are annotated; the eager classes call a function for `EagerMixin`'s `run()` (a mixin calling `super()` is not supported); the main makes the classes by name for the `BENCHMARKS` dict of classes; `math.factorial(500)`, a big int, becomes the factorial modulo a 53-bit prime by 64-bit multiplications, less work than CPython's. Arguments name the variant (or `all`), `tg` for task groups, and smaller levels and sleeps for smoke/GC runs; the normal run keeps six levels of six branches and 50 ms sleeps. Where pyperf's `bench_async_func()` awaits the loops in one event loop, the main runs each with `asyncio.run()`. The memoized keys and the next random number, which follow the order in which the leaves ran, are checked outside the timer. |
| `barnes_hut` | Integer zeros that become floats are float literals. Constructors, the particle list and the child nodes are annotated. |
| `bpe_tokeniser` | Five kernel adaptations: annotate the decoder field and empty ranks dictionary; type the pair `Counter`; materialize `zip` for `enumerate`; pass the UTF-8 replacement policy positionally. The runner exposes the unchanged pattern, permits smaller vocabularies, and takes an explicit corpus path instead of `__file__`. |
| `chaos` | A Park–Miller generator replaces `random.seed()` and `randrange()`, so the points differ from upstream. `GVector` has float parameters and defaults; `__rmul__ = __mul__` becomes a method; fields are annotated; loops replace two-clause comprehensions; `length` starts as `0.0`; `x` and `y` are converted to int in one assignment each; an impossible `type()` message is a literal. `main()` returns the game, whose `create_image_chaos()` the main times with the default arguments. |
| `comprehensions` | The empty widget list is annotated. The upstream `Enum` and enum iteration are restored. The complete sorted widget order is checked. |
| `coroutines` | The recursive `async def fibonacci()` and the `send(None)` loop that runs it are unchanged. An argument limits smoke/GC runs to `fibonacci(10)`; the normal run keeps `fibonacci(25)`. A second coroutine awaits `fibonacci()` outside the timer to check the result, because a coroutine's `StopIteration` carries no value in Pystachy. |
| `logging` | All three kernels run directly on the same `StringIO` stream. The driver checks every emitted line and verifies that disabled calls produce no output. |
| `generators` | The recursive `Tree`, `yield from`, range slicing and iteration are unchanged. A size argument limits smoke/GC runs to 100 nodes; the normal run keeps 100,000. The complete yielded sequence is checked outside the timer. |
| `json_dumps` | Opt into dynamic `Any`; annotate the empty dict and the list of `(Any, range)` workload tuples. Preserve all four upstream payloads and counts by default; smoke uses one encode per case and a three-element HUGE list. Complete small encodings and the repeated huge encoding are checked outside the timer. |
| `json_loads` | Opt into dynamic `Any` and annotate the fresh heterogeneous tuple. All keys in upstream `DICT` are strings, so `str(rand_val)` replaces the generic `type(key)(rand_val)` branch. Preserve `Random(5)`, all three payloads and the 20 unrolled loads per payload; decoded values are printed after timing. |
| `fannkuch` | None besides the runner. Upstream's reversing slice assignment replaced a copy-and-`reverse()` workaround on 31 October 2026 (`68f4ac9f`), which changed the timed work: timings of the earlier source, such as the [16 October snapshot](../../docs/benchmarks/pyperformance-2026-10-16-a74faae.json), are not comparable with later ones. |
| `float` | `self.x = x = sin(i)` is split so that fields can be annotated, and so are `__init__` and `points`. |
| `go` | The same generator replaces `random`, so the games differ from upstream. Fields set outside `__init__` are declared in the class body. `useful()` returns `bool(...)`, and `score()` counts in a float. `maxscore` starts as `-1.0`. The never-called `Board.check()`, whose sets hold `Square` objects, is commented out. |
| `hexiom` | A class-body default `HIGHEST_VALUE_STRATEGY` becomes its value, `2`. Conditional `range` values become lists, and `[None] * n` replaces `n * [None]`. Fields and constructors are annotated. `main()` returns the solution. |
| `meteor_contest` | `SE` is `51`, not `51.0`, because floats cannot be set elements or dict keys. Loops replace a two-clause comprehension and `dict()` of a generator expression. A list replaces another generator expression, and `''.join(reversed(s))` replaces `s[::-1]`. |
| `nbody` | None. |
| `nqueens` | `permutations()` and `n_queens()` return lists instead of yielding. `tuple()` takes a list comprehension. `reverse()` and concatenation replace a slice step and a slice assignment. |
| `pidigits` | The module opts in to [promoting ints](../../docs/python-int.md) with `# pystachy: python-int`, so the digits use CPython's arbitrary-precision `int`. A generator expression replaces `map(lambda k: ..., icount(1))`, which is equally lazy over the infinite count. Every computed digit is printed. |
| `raytrace` | A list replaces `array.array('B')`. `Vector` and `Point` have float coordinates, and the scene uses float literals. Class attributes are declared. Unreachable `Point` and `Vector` results are commented out of `Vector.__add__()` and `Point.__sub__()`. Raising a string becomes the `TypeError` it raises. Keyword parameters replace `**kwargs`, and the image is not written. |
| `regex_dna` | The sequence is an ASCII `str`, not bytes. The generator builds lists of strings, and the patterns are strings. |
| `regex_effbot` | A global replaces the function attribute `bench_regex_effbot.data`, and a loop replaces a dict comprehension. The `USE_BYTES` branches, never taken, are commented out. |
| `regex_v8` | None besides the checksum, computed after the timed loops because the blocks discard their results: substitution contents, search contents and positions, split pieces and boundaries, and module-level search/match/sub results. |
| `richards`, `richards_super` | Constructors, fields and the `Task` methods that inference needs are annotated. `BUFSIZE_RANGE` is a list. |
| `scimark` | Lists replace `array('d')` and `array('i')`. `Random`'s class constants are written out, and fields set by `initialize()` are declared. `ArrayList` no longer derives from `Array2D`, because its rows have a different type; its items are rows, and the inherited methods are copied. `indexes()` returns a list. `Array2D` is passed as `None` because classes are not values, and the `BENCHMARKS` table is replaced by the main. |
| `spectral_norm` | Accumulators and `u` start as floats. |
| `unpack_sequence` | A tuple literal replaces `tuple(range(10))`. The main runs upstream's default, `bench_all()`: the tuple and the list variants. |

The `random` substitutes produce 31-bit values, including `go`'s Zobrist hash strings.
Results within a benchmark are checked against CPython, not against upstream pyperformance.

<a id="blocked"></a>
<a id="current-runner-only-census"></a>
<a id="refresh-2026-11-02"></a>
<a id="runner-only-census-2026-10-22"></a>

## Census

These are recorded probes, last updated for `3aa7265a` on 2026-11-03; they are not
rerun automatically when the compiler changes. Use the [census command](#provenance)
with the pinned upstream sources to check today's first errors. The full byte-BPE
port above covers training, encoding and decoding; the earlier fixed-rank sample
below did not.

The same 52 upstream files were compiled on `8444af96` (before the stdlib additions)
and `3aa7265a` (with the argparse adapter). With only the runner replaced, both
compiled seven to IR: `fannkuch`, `generators`, `nbody`, `nqueens`, `regex_v8`,
`spectral_norm` and `unpack_sequence`. The original sdist run on `5eaf5638` found
the same seven. Eight of the other files advanced past a missing-module error:

| Previously missing | Benchmarks and next blockers |
|---|---|
| `argparse` | `argparse`: bare `list` return annotation |
| `copy` | `deepcopy`: bare `list` dataclass field |
| `enum` | `comprehensions`: empty widget list needs an annotation |
| `glob` | `2to3`: missing `subprocess` |
| `logging` | `logging`: dispatch table containing distinct function types |
| `pathlib` | `bpe_tokeniser`: decoder field needs an annotation; `pathlib`: missing `Path.stat()`; `tomli_loads`: missing `tomli` |

Separate import programs for `argparse`, `copy`, `enum`, `logging` and `pathlib`
executed in JIT. A separate pyperf 2.10.0 worker with psutil 7.2.2 ran under
CPython 3.13.16. Compiling that worker with Pystachy stopped at the missing
`sysconfig` import in pyperf.

The adapted suite uses CPython's output as the oracle in JIT and AOT. Three extra
samples also matched in both modes: BPE encoding with fixed ranks and materialized
`zip` pairs, deepcopy of the benchmark dataclass with a `list[int]` field, and
pathlib's eight-file setup followed by glob, binary reads and cleanup. These
samples exclude BPE training, copy reduction hooks and `Path.stat()`, respectively.

<a id="sources-without-a-delivered-port"></a>
<a id="scope-and-remaining-candidates"></a>

### Sources without a port

The middle column records the shipped-library result at the census revisions
above. The last column records the original `5eaf5638` probe with a CPython 3.13.18
stdlib overlay. “Same” describes that historical run. A source can have more
blockers than its first error, and a newer compiler may have removed one.

| Benchmark | First error with the shipped library | Historical overlay result |
|---|---|---|
| `2to3` | no `subprocess` module | `signal` imports the missing `_signal` |
| `argparse` | bare `list` return annotation on `generate_arguments()` | a bare `list` annotation (`-> list`) |
| `asyncio_tcp` | no `asyncio` module; with lib's `asyncio`, no `ssl` module | `socket` imports the missing `_socket` |
| `base64` | no `base64` module | `random.randbytes()` needs `int.to_bytes()` |
| `concurrent_imap` | no `multiprocessing` module | `signal` imports the missing `_signal` |
| `crypto_pyaes` | no `pyaes` module (third-party) | same |
| `decimal_factorial`, `decimal_pi`, `telco` | no `decimal` module | `contextvars` imports the missing `_contextvars` |
| `deepcopy` | a bare `list` annotation (`lst: list`) | a bare `list` annotation (`lst: list`) |
| `deltablue`, `typing_runtime_protocols` | unsupported base class | same |
| `gc_collect`, `gc_traversal` | no `gc` module | same |
| `mdp` | no `fractions` module | `contextvars` imports the missing `_contextvars` |
| `pathlib` | `Path.stat()` | `shutil` imports `bz2`, which imports the missing `_bz2` |
| `pickle` | no `pickle` module | `copyreg` keys a dict by classes |
| `pprint` | no `pprint` module | statements in the body of class `PrettyPrinter` |
| `pyflate` | no `hashlib` module | inheritance with generic class templates |
| `python_startup` | no `subprocess` module | `signal` imports the missing `_signal` |
| `regex_compile` | global `regexes` needs a type annotation | same |
| `sqlite_synth` | no `sqlite3` module | `sqlite3` imports the missing `_sqlite3` |
| `tomli_loads` | no `tomli` module (third-party) | no `tomli` module (third-party) |
| `xml_etree` | no `xml` module | `xml.etree.ElementTree` imports the missing `_elementtree` |

The argparse kernel also registers subparsers, argument groups and 1,000 options whose names
are built in a loop. These exceed the [static parser subset](../../lib/compatibility.md#argparse).
To reproduce its result from the pinned sdist:

```sh
python3 tools/bench_pyperformance.py --census pyperformance-1.14.0.tar.gz | grep -F '| `argparse` |'
```

When evaluating another port:

- Preserve the behavior being measured. Async/event-loop, process-pool, CPython GC,
  interpreter startup and database workloads need the corresponding runtime behavior;
  replacing it with a simpler kernel changes the benchmark.
- Keep the numeric semantics of `decimal_factorial`, `decimal_pi`, `telco` and the
  fractions-based `mdp`. Fixed-width substitutes change what they test. `pidigits`
  uses [promoting ints](../../docs/python-int.md) to retain CPython's `int` semantics.
- Check beyond the first error. For example, `regex_compile` also replaces another
  module's regex calls, so annotating its global alone does not complete the port.
- Account for external inputs and licenses. `crypto_pyaes` needs `pyaes`; `tomli_loads`
  needs `tomli` and a 16.8 MB fixture that is too large to vendor; `deltablue` is
  deferred for its [license provenance](#license). Shipping `tomllib` alone does
  not supply the benchmark's `tomli` dependency.

Related design and coverage history is in
[#361](https://github.com/den-run-ai/pystachy/issues/361) (benchmark coverage),
[#257](https://github.com/den-run-ai/pystachy/issues/257) (stdlib),
[#783](https://github.com/den-run-ai/pystachy/issues/783) (TOML),
[#805](https://github.com/den-run-ai/pystachy/issues/805) (copy/pickle dispatch) and
[#775](https://github.com/den-run-ai/pystachy/issues/775) (dynamic builtin values).

<a id="sources-with-delivered-ports-before-their-adaptations"></a>

### Ported sources before their adaptations

The recorded census also compiled the upstream file of each port. These were its
first errors before the adaptations; "none" means that replacing the runner was enough
at that revision.

| Benchmark | First error of the upstream file |
|---|---|
| `async_generators` | `async def` at `3aa7265a`, then `async generators are not supported`; none since async generators compile |
| `async_tree` | no `asyncio` module at `3aa7265a`; with lib's `asyncio`, inheritance with generic class templates (`AsyncTree`'s unannotated `__init__`) |
| `barnes_hut` | field `particles` needs a type annotation |
| `bpe_tokeniser` | field `_decoder` needs a type annotation |
| `chaos` | class attribute `__rmul__` needs a type annotation |
| `comprehensions` | empty `widgets` list needs a type annotation |
| `fannkuch`, `generators`, `nbody`, `nqueens`, `regex_v8`, `spectral_norm`, `unpack_sequence` | none |
| `float` | field `x` needs a type annotation |
| `go` | field `pos_child` needs a type annotation |
| `hexiom` | class attribute `HIGHEST_VALUE_STRATEGY` used as a class-body default |
| `json_dumps` | an empty dict needs a type annotation |
| `json_loads` | `expected int, got str` (line 50) |
| `logging` | dispatch table contains distinct function types |
| `meteor_contest` | `expected int, got float` (line 88) |
| `pidigits` | `map()` outside a call that takes its items at once |
| `raytrace`, `scimark` | no `array` module |
| `regex_dna` | `bytearray()` |
| `regex_effbot` | function attribute `bench_regex_effbot.data` |
| `richards`, `richards_super` | inheritance with generic class templates |

`python3 tools/bench_pyperformance.py --census pyperformance-1.14.0.tar.gz` prints each first
error in full.

## Recorded results

These comparisons describe their recorded compiler revisions and benchmark sources.
Use [Run](#run) to measure the current suite. Changes to port inputs or adaptations
require new measurements, even when the benchmark name stays the same.

<a id="alpha3-to-alpha4"></a>

### alpha.3 to alpha.4 (2026-11-02)

Across 22 comparable benchmarks, alpha.4 executed a geometric mean of **2.55% more
instructions** than alpha.3. Every measured output matched CPython 3.13.18. This is
an AOT instruction-count comparison; alpha.4 wall time and JIT performance were
not measured in this experiment.

The compilers of [v0.1.0-alpha.3](https://github.com/den-run-ai/pystachy/releases/tag/v0.1.0-alpha.3)
and [v0.1.0-alpha.4](https://github.com/den-run-ai/pystachy/releases/tag/v0.1.0-alpha.4),
each with its own library and runtime, built the same alpha.4-era benchmark sources.
Callgrind 3.22.0 measured the executables on 2026-11-02: x86-64 Linux, LLVM 18.1.3,
and a shared 4-vCPU Intel Xeon host at 2.10 GHz. The release-candidate measurement
used `ec442a20`, whose compiler, library, runtime and benchmark code matches the
alpha.4 tag.

The table gives **millions of whole-process instructions**, sorted by change.
Positive values mean more instructions; negative values mean fewer. `pidigits`
needed alpha.4's [promoting ints](../../docs/python-int.md); alpha.3 raised
`OverflowError`, so it has no comparable row. `logging` joined the suite after
this measurement. The table therefore does not cover the current 24-port suite.

| Benchmark | alpha.3 | alpha.4 | Change |
|---|---:|---:|---:|
| `generators` | 1,068.6 | 1,262.7 | +18.2% |
| `barnes_hut` | 768.5 | 854.6 | +11.2% |
| `go` | 350.2 | 377.9 | +7.9% |
| `json_dumps` | 1,440.5 | 1,514.0 | +5.1% |
| `nqueens` | 1,148.6 | 1,195.6 | +4.1% |
| `fannkuch` | 868.8 | 901.9 | +3.8% |
| `scimark` | 602.7 | 623.6 | +3.5% |
| `hexiom` | 689.3 | 710.7 | +3.1% |
| `meteor_contest` | 828.6 | 851.9 | +2.8% |
| `regex_effbot` | 1,648.7 | 1,680.5 | +1.9% |
| `nbody` | 570.5 | 580.5 | +1.8% |
| `float` | 339.5 | 344.6 | +1.5% |
| `regex_v8` | 15,371.7 | 15,600.8 | +1.5% |
| `regex_dna` | 1,176.3 | 1,183.9 | +0.6% |
| `unpack_sequence` | 1.2 | 1.2 | +0.4% |
| `spectral_norm` | 691.0 | 691.5 | +0.1% |
| `raytrace` | 681.9 | 680.4 | −0.2% |
| `json_loads` | 1,300.3 | 1,296.1 | −0.3% |
| `richards_super` | 676.8 | 672.4 | −0.7% |
| `richards` | 662.9 | 658.4 | −0.7% |
| `comprehensions` | 435.6 | 424.2 | −2.6% |
| `chaos` | 1,027.7 | 981.6 | −4.5% |
| **Geometric mean** | | | **+2.55%** |

#### Interpreting the counts

Recursion checks explain the largest increases. Alpha.4 enforced
`sys.setrecursionlimit()` in native code
([#996](https://github.com/den-run-ai/pystachy/pull/996)) and checked the native stack
([#1026](https://github.com/den-run-ai/pystachy/pull/1026)); alpha.3 ignored the limit.
`generators` paid on each recursive `yield from` resume, `barnes_hut` on recursive
force calculations, and `go` partly on recursion. Outside this suite,
`bench/fib.py` executed 37.9% more instructions.

The record also includes a separate pre-merge
[#1033](https://github.com/den-run-ai/pystachy/pull/1033) experiment: `generators`
was +13.3% and fib +24.1% relative to alpha.3. That PR subsequently
[merged on 2026-11-03](https://github.com/den-run-ai/pystachy/commit/5624ca0eb9db62fb9d1974d8ff154722b1201f6f).
Those figures describe the recorded experiment; the table above remains the
alpha.4 comparison, not a measurement of current `main`.

Allocation removal reduced `chaos`'s count by deleting unread objects containing
only numbers ([#1020](https://github.com/den-run-ai/pystachy/pull/1020),
[#1025](https://github.com/den-run-ai/pystachy/pull/1025)). The smaller increases above
2% were profiled only on an earlier candidate, `c3aaa068`, which lacked alpha.4's
last fixes; the [function-level attribution](results/alpha3-vs-candidate-2026-11-02.json)
therefore does not establish their causes on alpha.4.

Keep these measurement limits in view:

- **Instructions are not elapsed time.** Callgrind omits cache misses and branch
  prediction, and counts each byte cleared by `rep stosb`. In paired wall-time runs
  of the earlier `c3aaa068` candidate, `generators` was level despite +13% in
  instructions; `regex_dna` took 31% less wall time with almost the same count.
- **Whole-process counts include startup and output checks.** The untimed checksum
  pass dominates `regex_v8`; startup dominates `unpack_sequence`, whose unpacking
  AOT optimizes away. These counts differ from the runner's timed kernel sections.
- **The alpha.4 counts include a documented adjustment.** They subtract roughly
  100,000 instructions for a stack-bounds lookup triggered only under Valgrind.
  The raw record retains both the total and the subtracted cost for each executable.
- **Build time came from single builds on a shared host.** Executable size grew by
  a geometric mean of 12.35%; build wall time grew by 24.64%. The size ratio is
  deterministic; the wall-time ratio is not a reliable prediction for another run.

### Data and earlier results

The [release-candidate record](results/alpha3-vs-release-candidate-2026-11-02.json)
retains revisions, arguments, commands, binary hashes, counts, build measurements
and the Valgrind adjustment. Its original comparison scripts were temporary files
and are not in this repository. The [earlier candidate record](results/alpha3-vs-candidate-2026-11-02.json)
retains attribution, paired wall-time samples and additional reproduction details.

The 2026-10-16 CPython wall-time comparison and October regex reruns remain in the
[commit-pinned results page](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/docs/pyperformance.md).
Their raw samples remain in [`docs/benchmarks/`](../../docs/benchmarks/). These older
measurements use the sources and inputs recorded there; for current CPython, JIT
and AOT timings, run `make bench-pyperformance` as described [above](#run).
