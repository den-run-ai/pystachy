# Online call-site type tracing for shlex

This extends [the offline stream probe](stream-skew.md) with compilation during
application execution. The running native program observes the stream member at
the `tokenize` call site. After 100 observations, a member with at least 90%
share can trigger compilation and installation of a concrete call chain.

The measured prototype successfully compiled and installed during execution,
but was slower than generic AOT in all seven samples, including warm execution.
The results below do not establish a performance benefit for this workload.

The unit compiled is the original function and its ordinary helpers. This is
online type-feedback specialization of a whole call chain. It does not record
branch paths, perform on-stack replacement, or deoptimize midway through a
function. The possible reference-union members remain declared in the source.

## Execution and state

1. The initial executable contains the generic parser and the observer. The
   measured generic/online inputs contain no concrete control functions.
2. Calls 1–99 execute the generic native body. Before call 100 enters its body,
   the runtime checks the first observation window for sufficient skew.
3. A synchronous subprocess runs the self-hosted native compiler's internal
   `trace` command. It compiles the selected concrete template and helpers through
   the same typed IR and LLVM lowering, then produces a native shared object.
4. The host loads and validates that image, and call 100 can enter its compiled
   body. Later matching calls use the installed pointer. Other union members and
   `None` retain the original generic behavior.

There is one attempt per site, up to 16 sites. An unskewed first window disables
that site. A later distribution change does not trigger another compilation.
Compiler failure, a 60-second timeout, incompatible source/ABI, or failed loading
leaves the generic path available. Arguments are evaluated once before the
observer; neither compilation failure nor a callee exception replays the call.

The image links **no runtime** and runs no module initializer. It imports the
host's runtime, mutable globals, default values, and original literals/callable
singletons. The host's collector and exception machinery therefore remain the
only ones in use. The loaded image stays resident until process exit, including
its newly introduced immutable literals. Temporary files are normally removed
after loading; there is no persistent compiled-image cache.

The host embeds a bounded manifest containing exact parsed-source fingerprints,
compiler/runtime fingerprints, the selected compiler executable, relevant flags,
global types, class layouts, union/class/object IDs, literal identities and
eligible call-site signatures. The child first reproduces the ordinary baseline
and checks that manifest, then compiles the concrete body. A clone may add private
template classes, but may not introduce shared globals or runtime object
descriptors. Installation also checks the exact selected site and member.

The first tier supports **Linux AOT hosts** and one reference-union argument with
an integer result. The loaded code is generated at runtime; the host itself was
compiled ahead of time. Ordinary `pystachy run` remains a separate pre-execution
ORC JIT control. Online loading through `lli`, asynchronous compilation, broader
entry ABIs, arbitrary dynamic types, and speculative compiler-state rollback are
outside this prototype.

## Workload and comparison

The parser's existing `shlex.read_token()` body is unchanged. Each parse consumes
the same 9,440-byte ASCII document and yields 544 tokens. Exact token-list checks
against upstream CPython are separate from timed checksum loops.

Each measured process executes:

| Phase | Calls | Stream distribution |
| --- | ---: | --- |
| Cold | 200 | 199 memory, then 1 file |
| Warm | 4,000 | Memory |
| Shift | 40 | Alternating, then reversed skew: 11 memory / 29 file |
| Recovery | 4,000 | Memory |

The expected online result is one attempt/install at call 100, **8,111 loaded
entries and 129 generic entries**. That includes 99 generic warmup calls and all
30 file calls. Compilation occurs inside each measured process and is repeated
for each cold sample.

`tools/bench_stream_online.py` creates separate generic and concrete benchmark
inputs. It removes concrete control functions and redirects their call sites in
the generic/online input, while asserting that the `tokenize` AST is unchanged.
The concrete input is an exact copy of the original benchmark. Both input texts
and hashes are retained in the measurement record. This transformation only
separates benchmark controls; it does not generate a parser or replacement loop.

Samples rotate generic AOT, online AOT-host execution, and concrete AOT. Ordinary
generic/concrete ORC JIT runs are recorded separately. Process-wide wall time and
waited-child-inclusive CPU include online compilation; per-phase wall/self CPU
separate the pause from execution after installation. The runtime independently
records compilation wall/CPU and load time. `time.process_time()` alone would
omit the compiler subprocess and cannot establish online total cost.

The online image imports runtime functions across a shared-library boundary.
Unlike ordinary AOT, it cannot inline the host runtime into its parser. Warm
measurements therefore include this prototype's loading boundary as well as
specialization. An ordinary concrete AOT control is an upper bound on useful
specialization, not an equivalent code-generation tier.

## Reproduction

```sh
export PYSTACHY_LLVM=/path/to/llvm/bin
make
python3 tools/bench_stream_online.py \
  --compiler "$PWD/pystachy" --online-compiler "$PWD/pystachy"
make stream-online-check
```

The runner records raw samples, execution order, exact counters, build timings,
executable sizes, compiler identity and source hashes. It checks that the sources
and native compiler did not change during measurement. `--timing-cpu` selects an
allowed CPU; the default is the first CPU in the process's affinity set.

The compile-time flag is `PYSTACHY_ONLINE=1`, with the existing
`PYSTACHY_FEEDBACK_FUNCTION=tokenize` selection. Set
`PYSTACHY_ONLINE_COMPILER` to the same executable at host build and runtime.
`PYSTACHY_ONLINE_STATS` selects the exit TSV report. For diagnosis,
`PYSTACHY_ONLINE_KEEP=1` retains the private temporary directory and compiler log.

## Measured results

[The raw measurement](benchmarks/stream-online.json) contains seven rotated
AOT/online samples and three ordinary ORC JIT samples on Linux x86-64 with LLVM
18.1.3, pinned to allowed CPU 0. Other local test/bootstrap jobs had finished.
Compiler, runtime, workload and native-compiler hashes remained unchanged across
the run. An untimed, separately recorded ORC check prepared its shared runtime
object cache before measurement; each ORC sample still includes its own program
compilation before entry. Online samples each compile a fresh image.

Times below are seconds, shown as **median [minimum, maximum]**. Whole-process
measurements include startup and untimed token validation; CPU includes waited
compiler descendants.

| Mode | Whole-process wall | Inclusive CPU |
| --- | ---: | ---: |
| Generic AOT | 4.292 [4.134, 4.962] | 4.286 [4.132, 4.956] |
| Online AOT host | 6.361 [6.049, 7.288] | 6.360 [6.046, 7.281] |
| Concrete AOT control | 4.398 [3.881, 4.516] | 4.395 [3.874, 4.514] |
| Ordinary generic ORC JIT | 5.668 [5.348, 5.903] | 5.667 [5.346, 5.902] |
| Ordinary concrete ORC JIT | 5.888 [5.870, 6.196] | 5.887 [5.869, 6.195] |

The phase wall clocks separate compilation from subsequent execution:

| Phase | Generic AOT | Online AOT host | Concrete AOT control |
| --- | ---: | ---: | ---: |
| Cold, 200 calls | 0.111 [0.107, 0.130] | 0.543 [0.499, 0.602] | 0.111 [0.102, 0.144] |
| Warm, 4,000 calls | 2.010 [1.949, 2.361] | 3.104 [2.666, 3.503] | 2.082 [1.873, 2.351] |
| Shift, 40 calls | 0.024 [0.021, 0.035] | 0.025 [0.023, 0.037] | 0.024 [0.020, 0.031] |
| Recovery, 4,000 calls | 2.123 [1.990, 2.476] | 2.871 [2.682, 3.138] | 2.005 [1.876, 2.223] |

Runtime compilation took **0.402 [0.369, 0.454] seconds wall** and
**0.395 [0.363, 0.445] seconds CPU**. Loading took
**0.116 [0.106, 0.146] milliseconds**. These costs are already included in the
online cold phase and whole-process measurements.

The paired generic/online wall ratios were **0.683 [0.588, 0.756]** overall,
**0.729 [0.574, 0.783]** in the warm phase, and
**0.761 [0.683, 0.847]** in recovery. A ratio below one means online execution
took longer. Online was slower in every pair, including both long phases after
installation; these observations support no amortization point for this workload. The paired
generic/concrete AOT ratio was **1.028 [0.929, 1.136]**, and the ordinary ORC
ratio was **0.963 [0.863, 1.006]**. Those concrete controls show no consistent
advantage. The measurements do not isolate how much of online's extra execution
cost comes from its shared-library boundary, dispatch, or other code-generation
differences.

Every online process recorded exactly **8,240 calls, one attempt, one install at
call 100, 8,111 loaded entries and 129 generic entries**, with no failure. Thus
the changed stream mix exercised fallback and recovery without recompilation.
The benchmark's full token-list oracle runs before online installation; timed
calls validate a checksum of token lengths. They do not individually compare
every token's contents. Host IR inspection also confirmed one generic tokenizer,
no concrete control definitions, and an indirect call through the installed
entry pointer.

A separate untimed integration test compared all 544 tokens on each of 110
calls, covering 99 generic warmup calls, eight loaded entries and three file
fallbacks. It passed with both native and hosted host compilation, each using
the native compiler for the loaded image.

The generic, online and concrete-control executables were **301,416, 674,320 and
313,832 bytes** respectively. The online host grew by 372,904 bytes; this includes
its manifest and exported runtime and excludes the separately loaded image.
Single, untimed host builds took 3.038, 4.327 and 3.559 seconds respectively;
these build observations are not a repeated compilation benchmark.

## Validation and CI routing

- Three-stage compiler and runtime IR fixed points passed.
- The native default JIT/AOT corpus passed **2,859 checks, zero failures**.
- All **eight online integration tests** passed with hosted and native host
  compilers. They cover the exact activation boundary, shared globals/defaults
  and identities, GC, exceptions without replay, changed stream distributions,
  compilation/loading failures and incompatible source layouts. The expanded
  full-document token test was rerun successfully in both configurations.
- The **11 offline feedback integration tests** still pass with the native
  compiler. Runtime signature/effect checks, strict C syntax, Ruff and whitespace
  checks passed.

The prior draft's GitHub contracts/benchmark failures came from default
`bench/*.py` consumers treating this opt-in fixture as an ordinary benchmark.
Those default selectors now exclude this one file. Explicit file selections
remain available. CI retains mandatory `stream-feedback-check` and
`stream-online-check` targets, which supply the feature flags and the upstream
CPython `shlex` adapter. The measured source path and contents are unchanged.
