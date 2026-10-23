# pyperformance benchmarks

These are 22 of the 52 benchmarks tried from [pyperformance](https://github.com/python/pyperformance)
1.14.0, adapted so that Pystachy compiles them. CPython runs the same adapted files, so each
comparison runs identical source in CPython, the JIT and AOT. The adaptations and smaller
inputs change the work, so these results are not comparable with published pyperformance numbers.
The measurements are in [pyperformance results](../../docs/pyperformance.md).

The 52 are the 31 benchmarks that this port set out to try, mostly CPU-bound and often cited,
and the 21 others that need no third-party package. The release's other 21 benchmarks list third-party
packages in their `requirements.txt` and are outside this runner's census: `asyncio_websockets`, `chameleon`,
`coverage`, `dask`, `django_template`, `docutils`, `dulwich_log`, `fastapi`, `genshi`,
`hg_startup`, `html5lib`, `mako`, `networkx`, `sphinx`, `sqlalchemy_declarative`,
`sqlalchemy_imperative`, `sqlglot_v2`, `sympy`, `tornado_http`, `xdsl` and `yaml`.
Their package dependencies need a separate assessment; exclusion from this census is not a
measured compiler rejection.

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

## Provenance

The sources are `pyperformance/data-files/benchmarks/bm_NAME/run_benchmark.py` from the
pyperformance 1.14.0 sdist, `pyperformance-1.14.0.tar.gz`, SHA-256
`91f74393997b604375ad5b79bf569a24076d70181c076a53abad5383a238a8aa`. Given that sdist,
`python3 tools/bench_pyperformance.py --census pyperformance-1.14.0.tar.gz` checks these hashes,
checks that each changed hunk of a port carries a `# Pystachy port:` note and that each port
times what pyperf times, and compiles each upstream file with only pyperf's runner replaced,
reporting the first compiler error.

| Benchmark | Upstream SHA-256 | Status |
|---|---|---|
| `2to3` | `a491c6dfe070a073cae07fc07f903afcc6d795207f2c70ab96f0ac0d9363d916` | blocked |
| `argparse` | `f914991901e5a24d536753c3b2b5229b1e9e5d4d982ba82da2e1cfbbf3677feb` | blocked |
| `async_generators` | `0441979a5ffc49c1e44539f5cb5a082bb70fcef5627619872feb4f3901351de5` | blocked |
| `async_tree` | `7c1493bc27c5c41f70f51cbf46a33c77b791915364ce619231461441f042178b` | blocked |
| `asyncio_tcp` | `fa993861ad75dcd724d282442e671095ad708a9dcb87e4314831d04006ad4a23` | blocked |
| `barnes_hut` | `802a1c170b82a5d82ea69b7a893f09d4b50b4f232e20a8e1c1bb8b2c04e6af1d` | ported |
| `base64` | `e2f1e7d4dbfbb2c722833081496497344550e4367f85f67f373fb8aa22cd35ed` | blocked |
| `bpe_tokeniser` | `c7255345499e118181785370b0996e8cc1056491b9678b3fbeb02421e3f9b2df` | blocked |
| `chaos` | `5d20fd29c8ea89e0ebe4040ae4c05f26f1a620cd2a7fc654d9d7f8cb205651ac` | ported |
| `comprehensions` | `6047efc06287a24a646f00fc8a8d47429f7cdeab3e942230e13cf6d7cefa6343` | ported |
| `concurrent_imap` | `d5bfb854e7a1d754f3033132dca397704ea7ed2aabfd6d625396b61b82a9e316` | blocked |
| `coroutines` | `9358a7d967ed16859b5a163a4e416d897d6f104b3603c56ad77903791211fc7f` | blocked |
| `crypto_pyaes` | `236222412fd81b5e13d9c818574b575809eccff17419d667f34cf0e9148aa724` | blocked |
| `decimal_factorial` | `0b88119beb7a2151ef59f0d7d969e655850d9aeef143426efd0e0a656b2bbcc6` | blocked |
| `decimal_pi` | `eb3974785e602143f16fcfbd07ffd8b742b326096d9fd914c59a79531175104c` | blocked |
| `deepcopy` | `9e1550442cbccfaff8a4988936487c091ac18bcc9c8ebdc41c1cb747c14ea078` | blocked |
| `deltablue` | `70da5e16cd5b14f2f398ccc066794b83a30d997c2d91150695b8f938f934dc30` | deferred: licence provenance |
| `fannkuch` | `2a8e4bc4c5e7e8ac605a4ca8246cc4baeab5336ac986d976e33657162750e8bf` | ported |
| `float` | `b4f61a0978f5b0af2c0d07544ae26422868992e62b8f40e2967e3c694fc1b9a9` | ported |
| `gc_collect` | `7886042f07e517abb79c58643a4b488710f3079936c6990522624bfb9c2acb9b` | blocked |
| `gc_traversal` | `0798ab87ca12687c68e101d14ae9ac0c50eaa9b4f14ecee3882f7e499191828f` | blocked |
| `generators` | `46c59dc44cb63b2c0fed75e6d82875daa237a92d03c87861078513c7b10d4621` | ported |
| `go` | `ea4c0ebaf32515f8549c64c9291ab13d47bb802e01a82203c37b5066d1bfb463` | ported |
| `hexiom` | `d7518220380d27449b8951bc9ca2e19593569d9bd9f5cb6d86867f354f22e115` | ported |
| `json_dumps` | `023c991ff827fdcbfcfb2b7e3cadf023352a61d1903643d8af0ef302a0db1bf7` | ported |
| `json_loads` | `16c41ff06bf3173d30158c767340d389c459a656e997e306719891d50f09646f` | ported |
| `logging` | `6ff62fdc4c6b520b01475407b526ed609299402ed8ad8d344038b559a120159a` | blocked |
| `mdp` | `3db5bfb8c9e2602f181cee809c24b2bd61e7c088e89e8e22867b8d46c4d0fcf1` | blocked |
| `meteor_contest` | `b616f5f87e129a6b35650452951f40a7812cf22efff5a0777e51287da13c2f48` | ported |
| `nbody` | `d1385e816d7cfea361b7915e2cf70138cd6b84f40df8bd5152638851f7bcac2b` | ported |
| `nqueens` | `f50ef0d82036790c99f5469b9cffc368e097de860231b328caa6652183af059e` | ported |
| `pathlib` | `113a1cbbec13165dfdb84db649d8114279460110733957a3749ffb9c9527612d` | blocked |
| `pickle` | `31c0e30be79514b45db0d4e858632eb429b0fea3edbac6463ad5f34d92f3cab8` | blocked |
| `pidigits` | `4bf89183acb8651623676ece6e10787b6c71eec549fe53ce17a62a812ef7447d` | blocked |
| `pprint` | `07ef57201c7919aedf9e340c7fb1561a40dfee698818c9694930f3e427091d6d` | blocked |
| `pyflate` | `ec5347c7045af86ba33e1b2c6f64bc4b506d0ade3b77391d7e41863fe25fb464` | blocked |
| `python_startup` | `4cc396c9fe32d633a5e902c8ca738391a4cfe80b6d7658a9d9048989fc796d0c` | blocked |
| `raytrace` | `88ef4d9060d8e8f6ce40f376477aaf89cc808fa44813225a3071a05a1467f017` | ported |
| `regex_compile` | `cdbc509e515840e469209ed5fc77ca3fe352278203cc1a7dad874db4e863dc6c` | blocked |
| `regex_dna` | `d820dbdf12262cd11a543ae3dc3fd85793a20220d5a15ef687d8ef57a75c97c6` | ported |
| `regex_effbot` | `0823b6507f8babea2238847562d9c9af31000ea57cbb695e5d47053321ea68c7` | ported |
| `regex_v8` | `c22f820cb9a031a892ec0341eecca81c758dc25ee5413613d18eddfdff54a491` | ported |
| `richards` | `a4512668525331960c54043b5150a3fff92badaeaba850a941893ac69a1028d8` | ported |
| `richards_super` | `665b3d5551171e147c127b6f8671edc9a7703c736d317cc4a991bb00f599dc36` | ported |
| `scimark` | `427b21b8a3802418ea3c2fe584335658a6c91c7f74fce4df9410efa60cd84d6e` | ported |
| `spectral_norm` | `a3390ec6d75606fec30c4b59ad5f77d5292cd8e36f445197232a34560a880b18` | ported |
| `sqlite_synth` | `dcba7a6889e66f08480f4332860208d624678fc42a03be5c8f3b6f1f894231fd` | blocked |
| `telco` | `a3acb202b3d4eb750aca977ce354f8ecc1f6adae17a695ed2e5be615e4797605` | blocked |
| `tomli_loads` | `a94f7368f9656044f45244eb71da4f29a785c154c4a75aa15ca5c0e3c609c0d0` | blocked |
| `typing_runtime_protocols` | `dfc0cbd25f2968ee6982ff93adde92a1fa2a56ffbed6dde2d1f9cb853c340961` | blocked |
| `unpack_sequence` | `0dafe97531abc4a5baf30fe011db7acb3bf1e64cd4e41acb0c7db2bb141a8382` | ported |
| `xml_etree` | `1d824c4d4dd92a7598e085dbdf7beed3809a75e4d6972c90377822c78f73477c` | blocked |

## License

pyperformance is distributed under the MIT License; [LICENSE](LICENSE) and [AUTHORS](AUTHORS)
are its `COPYING` and `AUTHORS` files. Each port keeps its upstream header. `regex_v8.py`'s
header carries the V8 project's BSD license, and `raytrace.py`'s states the MIT License.
`deltablue` is excluded pending a separate provenance decision: its upstream docstring
says the JavaScript original was GPL-licensed. The other 22 benchmarks remain included.
`fannkuch.py`, `meteor_contest.py`, `nbody.py`, `regex_dna.py` and `spectral_norm.py` say they
come from The Computer Language Benchmarks Game, whose programs are published under the
3-clause BSD License. `richards.py` and `richards_super.py` credit a Java version
"Copyright (C) 1995 Sun Microsystems, Inc.", and `chaos.py` says "Copyright (C) 2005 Carl
Friedrich Bolz". pyperformance distributes all of these files under its MIT License; their
origins are listed so that a license review can confirm that this suffices. See
[THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

## Adaptations

Each edit is marked `# Pystachy port:` in the source. These describe the delivered files,
including historical workarounds; newer compiler features make some unnecessary. In particular,
generators, range values and slice assignment now work for the runner-only sources listed below.
The runner adaptations follow these rules:

- `import pyperf` is removed. A main that reads the loop count and sizes from `sys.argv`
  replaces `pyperf.Runner` and prints the results, or a checksum.
- The seconds the main prints are for the part that pyperf would time. Where the runner calls
  `bench_func()`, the main times a loop of calls of that function and nothing else. Where it
  calls `bench_time_func()`, each benchmark function keeps its own timer around the same loop,
  with `time.perf_counter()`, which is `pyperf.perf_counter()`. Instead of returning the
  seconds, it appends them to a list `TIMED`, whose sum the main prints, and returns its result,
  or a checksum when it discards its result. `TIMED_PART` in `tools/bench_pyperformance.py`
  records which function each port times; the unit tests check the ports against it, and
  `--census` checks it against the upstream files.
- In older ports, `range_it = range(loops)` became a list because range values were not yet supported.
  The newly added ports retain range values.

| Benchmark | Other adaptations |
|---|---|
| `barnes_hut` | Integer zeros that become floats are float literals. Constructors, the particle list and the child nodes are annotated. |
| `chaos` | A Park–Miller generator replaces `random.seed()` and `randrange()`, so the points differ from upstream. `GVector` has float parameters and defaults; `__rmul__ = __mul__` becomes a method; fields are annotated; loops replace two-clause comprehensions; `length` starts as `0.0`; `x` and `y` are converted to int in one assignment each; an impossible `type()` message is a literal. `main()` returns the game, whose `create_image_chaos()` the main times with the default arguments. |
| `comprehensions` | Integer kind tags and an explicit two-kind list replace `Enum` and enum iteration; the widget list is annotated. Dataclasses, nested comprehensions, optional widget lookups and tuple sorting remain. The complete sorted widget order is checked. |
| `generators` | The recursive `Tree`, `yield from`, range slicing and iteration are unchanged. A size argument limits smoke/GC runs to 100 nodes; the normal run keeps 100,000. The complete yielded sequence is checked outside the timer. |
| `json_dumps` | Opt into dynamic `Any`; annotate the empty dict and the list of `(Any, range)` workload tuples. Preserve all four upstream payloads and counts by default; smoke uses one encode per case and a three-element HUGE list. Complete small encodings and the repeated huge encoding are checked outside the timer. |
| `json_loads` | Opt into dynamic `Any` and annotate the fresh heterogeneous tuple. All keys in upstream `DICT` are strings, so `str(rand_val)` replaces the generic `type(key)(rand_val)` branch. Preserve `Random(5)`, all three payloads and the 20 unrolled loads per payload; decoded values are printed after timing. |
| `fannkuch` | The reversing slice assignment uses a slice, `reverse()` and concatenation. |
| `float` | `self.x = x = sin(i)` is split so that fields can be annotated, and so are `__init__` and `points`. |
| `go` | The same generator replaces `random`, so the games differ from upstream. Fields set outside `__init__` are declared in the class body. `useful()` returns `bool(...)`, and `score()` counts in a float. `maxscore` starts as `-1.0`. The never-called `Board.check()`, whose sets hold `Square` objects, is commented out. |
| `hexiom` | A class-body default `HIGHEST_VALUE_STRATEGY` becomes its value, `2`. Conditional `range` values become lists, and `[None] * n` replaces `n * [None]`. Fields and constructors are annotated. `main()` returns the solution. |
| `meteor_contest` | `SE` is `51`, not `51.0`, because floats cannot be set elements or dict keys. Loops replace a two-clause comprehension and `dict()` of a generator expression. A list replaces another generator expression, and `''.join(reversed(s))` replaces `s[::-1]`. |
| `nbody` | None. |
| `nqueens` | `permutations()` and `n_queens()` return lists instead of yielding. `tuple()` takes a list comprehension. `reverse()` and concatenation replace a slice step and a slice assignment. |
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

## Runner-only census (2026-10-22)

Refreshed against compiler sources on main `5f7ec761`, with CPython 3.13.16 and the
pinned pyperformance 1.14.0 sdist. The census checks all 52 source hashes and replaces
only pyperf's runner/import before asking for IR. No installed-stdlib or ports overlay
is supplied: missing modules describe the shipped surface, not whether an explicitly
supplied upstream module could compile.

**Seven of 52 sources compile with runner replacement alone:** `fannkuch`, `generators`,
`nbody`, `nqueens`, `regex_v8`, `spectral_norm` and `unpack_sequence`. This is one more
than the 2026-10-17 census (`spectral_norm`). The other 45 have a compile error. An IR
success is not an execution result. The delivered suite now has **22 adapted benchmarks**,
including four additions: `comprehensions`, `generators`, `json_dumps` and `json_loads`.
Their CPython, native JIT and AOT outputs are compared by the existing smoke runner;
this does not execute the upstream pyperf harness or establish a speedup.

The two JSON benchmarks now exercise boxed heterogeneous documents using the explicit
experimental dynamic-`Any` opt-in; this does not change the feature's stability status.
The JSON timings preserve upstream's timed operations and default data shapes; setup
and new correctness checks remain outside those regions. `comprehensions` retains its
nested comprehensions and tuple sorting with small enum/annotation adaptations, while
`generators` needs no algorithm/type changes.

### Scope and remaining candidates

- Defer async/event-loop, process/thread-pool, CPython GC/startup and external-database
  workloads: `async_generators`, `async_tree`, `asyncio_tcp`, `coroutines`,
  `concurrent_imap`, `gc_collect`, `gc_traversal`, `python_startup`, `2to3` and
  `sqlite_synth`. Their dependencies are outside this expansion, not silently passed.
- Keep arbitrary-precision/decimal workloads blocked: `decimal_factorial`, `decimal_pi`,
  `telco`, `pidigits` and the fractions-based `mdp`. Replacing their arithmetic with
  fixed-width floats/ints would change what they test.
- Remaining core candidates need missing APIs or additional adapters: `argparse`,
  `base64`, `bpe_tokeniser`, `deepcopy`, `logging`, `pathlib`, `pickle`, `pprint`,
  `pyflate`, `regex_compile`, `tomli_loads`, `typing_runtime_protocols` and `xml_etree`.
  JSON's progress does not imply general copy/pickle dispatch or runtime reflection.
  `regex_compile` also captures and patches another module's regex calls; a list
  annotation alone does not deliver its dependency fixtures and behavior. `tomli_loads`
  still requires file/path setup, the pinned large TOML fixture and parser parity.
- `crypto_pyaes` requires its separate package adaptation. The existing 21
  third-party-package exclusions listed above are unchanged; `deltablue` remains
  excluded for its license provenance. No new module-support claim follows from this census.

The table records the first error, not all blockers. Related trackers:
[#361](https://github.com/den-run-ai/pystachy/issues/361) (benchmark coverage),
[#257](https://github.com/den-run-ai/pystachy/issues/257) (stdlib),
[#783](https://github.com/den-run-ai/pystachy/issues/783) (TOML),
[#805](https://github.com/den-run-ai/pystachy/issues/805) (copy/pickle dispatch),
[#775](https://github.com/den-run-ai/pystachy/issues/775) (dynamic builtin values).

### Sources without a delivered port

| Benchmark | First compiler result |
|---|---|
| `2to3` | `bm_2to3.py:1: error: module 'glob' is not supported` |
| `argparse` | `bm_argparse.py:9: error: module 'argparse' is not supported` |
| `async_generators` | `bm_async_generators.py:21: error: async functions are not supported` |
| `async_tree` | `bm_async_tree.py:20: error: module 'asyncio' is not supported` |
| `asyncio_tcp` | `bm_asyncio_tcp.py:9: error: module 'asyncio' is not supported` |
| `base64` | `bm_base64.py:10: error: module 'base64' is not supported` |
| `bpe_tokeniser` | `bm_bpe_tokeniser.py:16: error: module 'pathlib' is not supported` |
| `concurrent_imap` | `bm_concurrent_imap.py:6: error: module 'multiprocessing' is not supported` |
| `coroutines` | `bm_coroutines.py:10: error: async functions are not supported` |
| `crypto_pyaes` | `bm_crypto_pyaes.py:10: error: module 'pyaes' is not supported` |
| `decimal_factorial` | `bm_decimal_factorial.py:17: error: module 'decimal' is not supported` |
| `decimal_pi` | `bm_decimal_pi.py:19: error: module 'decimal' is not supported` |
| `deepcopy` | `bm_deepcopy.py:9: error: module 'copy' is not supported` |
| `deltablue` | `bm_deltablue.py:26: error: unsupported base class` |
| `gc_collect` | `bm_gc_collect.py:2: error: module 'gc' is not supported` |
| `gc_traversal` | `bm_gc_traversal.py:2: error: module 'gc' is not supported` |
| `logging` | `bm_logging.py:18: error: module 'logging' is not supported` |
| `mdp` | `bm_mdp.py:3: error: module 'fractions' is not supported` |
| `pathlib` | `bm_pathlib.py:10: error: module 'pathlib' is not supported` |
| `pickle` | `bm_pickle.py:253: error: module 'pickle' is not supported` |
| `pidigits` | `bm_pidigits.py:22: error: map() is unsupported in this value position` |
| `pprint` | `bm_pprint.py:9: error: module 'pprint' is not supported` |
| `pyflate` | `bm_pyflate.py:19: error: module 'hashlib' is not supported` |
| `python_startup` | `bm_python_startup.py:19: error: module 'subprocess' is not supported` |
| `regex_compile` | `bm_regex_compile.py:23: error: cannot infer the type of 'regexes', which capture_compile() reads, where it is defined: annotate it (regexes: T = ...)` |
| `sqlite_synth` | `bm_sqlite_synth.py:9: error: module 'sqlite3' is not supported` |
| `telco` | `bm_telco.py:18: error: module 'decimal' is not supported` |
| `tomli_loads` | `bm_tomli_loads.py:12: error: module 'pathlib' is not supported` |
| `typing_runtime_protocols` | `bm_typing_runtime_protocols.py:38: error: unsupported base class` |
| `xml_etree` | `bm_xml_etree.py:220: error: module 'xml' is not supported` |

### Sources with delivered ports, before their adaptations

Existing adaptations remain covered even where runner replacement now suffices.
Removing historical workarounds or restoring different inputs needs separately refreshed
checksums and timing records.

| Benchmark | First compiler result |
|---|---|
| `barnes_hut` | `bm_barnes_hut.py:78: error: cannot infer the type of field 'particles'; annotate it (self.particles: T = ...) (QuadTree(Rectangle[float, float, float, float], int) for the call at bm_barnes_hut.py:318; compiling advance_system(list[Particle-1], float, float, int, int) for the call at bm_barnes_hut.py:350; compiling bench_quadtree_nbody(int, int, int, float) for the call at bm_barnes_hut.py:366)` |
| `chaos` | `bm_chaos.py:46: error: cannot infer the type of class attribute '__rmul__'; annotate it (__rmul__: T = ...)` |
| `comprehensions` | `bm_comprehensions.py:8: error: module 'enum' is not supported` |
| `fannkuch` | Compiles after runner replacement |
| `float` | `bm_float.py:16: error: cannot infer the type of field 'x'; annotate it (self.x: T = ...) (Point(int) for the call at bm_float.py:49; compiling benchmark(int) for the call at bm_float.py:58)` |
| `generators` | Compiles after runner replacement |
| `go` | `bm_go.py:326: error: cannot infer the type of field 'pos_child'; annotate it (self.pos_child: T = ...)` |
| `hexiom` | `bm_hexiom.py:151: error: class attribute 'HIGHEST_VALUE_STRATEGY' of 'Done' used in a class-body default is not supported` |
| `json_dumps` | `bm_json_dumps.py:7: error: cannot infer the type of an empty dict; add a type annotation (d: dict[K, V] = {}, or -> dict[K, V] on a function returning the dict)` |
| `json_loads` | `bm_json_loads.py:50: error: expected int, got str` |
| `meteor_contest` | `bm_meteor_contest.py:88: error: expected int, got float` |
| `nbody` | Compiles after runner replacement |
| `nqueens` | Compiles after runner replacement |
| `raytrace` | `bm_raytrace.py:11: error: module 'array' is not supported` |
| `regex_dna` | `bm_regex_dna.py:135: error: unsupported call bytearray()` |
| `regex_effbot` | `bm_regex_effbot.py:156: error: type <function bench_regex_effbot> has no attribute 'data'` |
| `regex_v8` | Compiles after runner replacement |
| `richards` | `bm_richards.py:176: error: inheritance with generic class templates is not supported: annotate __init__ parameters with concrete types (not Any or object)` |
| `richards_super` | `bm_richards_super.py:177: error: inheritance with generic class templates is not supported: annotate __init__ parameters with concrete types (not Any or object)` |
| `scimark` | `bm_scimark.py:1: error: module 'array' is not supported` |
| `spectral_norm` | Compiles after runner replacement |
| `unpack_sequence` | Compiles after runner replacement |
