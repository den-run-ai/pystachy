# constargs: tests the whole program decides, 2026-11-13

`constargs` ([typed IR](../../../docs/typed-ir.md#constargs)) decides the tests of
parameters, fields and results that a program leaves at one constant, and LLVM then
discards the functions that only the decided branches called. This file records what
that changes and what it costs.

**Result.** A program that calls the json_repair port without a schema builds in
10.3 s instead of 22.9 s, as a 644 KB executable instead of 1,256 KB, and its first JIT
run takes 2.8 s instead of 6.2 s. Repair speed does not change. Across the test corpus
and the benchmarks, 439 of 2,381 programs keep less IR and none keeps more; the
compiler's frontend takes 3.9% longer in total, and 6.6% longer on its own source.

## Inputs and host

| Item | Value |
|---|---|
| Measured compiler | `6d82f404` (this branch), bootstrapped with `make` |
| Port program | `ports/json_repair` at `719cd1ba` ([#1296](https://github.com/den-run-ai/pystachy/pull/1296)) with this branch's compiler changes applied; not merged |
| Host | Linux x86-64 container, 4 CPUs (Intel Xeon 2.10 GHz), 15 GiB |
| Toolchain | LLVM 18.1.3; CPython 3.13.18 (the pin is 3.13.16) |
| Control | the same compiler with `PYSTACHY_OPT=-constargs` |
| Later commits | The commit after the measured one takes the functions to read from a worklist instead of rescanning them all. Its compiler emits the same IR, messages and exit status as `6d82f404`'s for all 4,484 programs of the corpus, with `PYSTACHY_IRCHECK=1`. |

Timings are wall time on one CPU (`taskset -c 2`), the median of three runs unless
stated. One host and one day: differences of a few percent are within its noise.

## The json_repair port

The program is `from json_repair import repair_json` and one call,
`print(repair_json('{"a": [1, 2, 3,], b: tru'))`. `repair_json` tests `schema` and
passes it on; the parser tests its `schema_repairer` field, which only
`parse_with_schema()` assigns; `_resolve_schema_for_parse()` returns that field as an
item of a tuple. With every one of those tests decided, schema repair, the validator
and `re` have no caller.

| Measure | `-constargs` | Default | Change |
|---|---:|---:|---:|
| IR lines that `globaldce` keeps | 166,692 | 49,025 | -71% |
| of them `re` | 89,623 | 1,187 | |
| of them the validator and schema repair | 23,915 | 709 | |
| `pystachy build`, wall | 22.86 s | 10.31 s | -55% |
| frontend | 1.81 s | 1.90 s | +0.09 s |
| LLVM optimization | 10.82 s | 4.27 s | |
| code generation | 8.64 s | 3.46 s | |
| Executable | 1,256,200 bytes | 644,160 bytes | -49% |
| `pystachy run`, program cache off | 6.24 s | 2.77 s | -56% |
| 200 repairs of a 400-record document (five runs) | 0.492 s | 0.479 s | within noise |

The IR counts are from `tools/inspect_compiler.py` output, counted as
`bench/constargs/kept_ir.py` counts them. A program that passes a schema keeps all of
it: the port's schema test and its corpus replay pass in JIT and AOT, with the pass on
and with `PYSTACHY_OPT=-constfold`.

## The corpus

```sh
python3 bench/constargs/kept_ir.py --jobs 4 tests/programs/*/*.py bench/*.py bench/pyperformance/*.py
```

| Measure | Value |
|---|---|
| Programs | 2,381 |
| Kept IR lines | 12,234,959 → 12,130,966 (-0.8%) |
| Programs that keep less, more, the same | 439, 0, 1,942 |
| Smallest kept ratio | 0.797 |
| Frontend, summed (four at a time) | 64.7 s → 67.2 s (+3.9%) |

The programs that gain are those that use part of a library: `lib_functools.py` keeps
86%, the `logging` tests 98%. A program that uses all of what it loads gains nothing.
The compiler is such a program: its IR is the same byte for byte with the pass on and
off.

## Cost

| Program | Frontend, `-constargs` | Default | Change |
|---|---:|---:|---:|
| `pystachy.py` (3,690 functions, about a million ops) | 5.25 s | 5.60 s | +6.6% |
| `tests/programs/library/lib_logging_config.py` | 1.26 s | 1.22 s | within noise |
| `tests/programs/library/lib_tomllib.py` | 0.49 s | 0.54 s | +0.05 s |
| `tests/programs/library/lib_functools.py` | 0.079 s | 0.088 s | +0.009 s |

Median of five runs. The compiler's self-compilation with a collection every 5,000
allocations (`gc-self`) runs 4,063 collections with the pass and 4,055 without it.

A function of more than 4,096 ops is read as written. Without that bound,
`lib_tomllib.py` kept 3% less IR and its frontend took about 0.12 s longer: nearly all
of it went to `re`'s matcher, a function of 9,300 ops and 1,790 blocks.

## Validation

- `make`: the compiler and `runtime.py` reach their IR fixed points with the pass on.
- `make test`: 7,098 passed, 0 failed (JIT and AOT).
- `PYSTACHY_OPT=-constfold make test`: 7,098 passed, 0 failed. In this mode every block
  and edge that the pass decided cannot run exits with an error instead, so no test of
  the corpus runs such code.
- A planted bug: with the pass blinded to the stores of fields, a program that sets a
  field and then tests it printed a wrong result by default and stopped with the error
  under `-constfold` (CPython-hosted compiler, JIT). `tools/test_typed_ir_constargs.py`
  checks that the error is placed where the wrongly decided test goes.
- `make lint check-fast check-ir check-runtime check-repository`: pass; `check-ir`
  accepts 2,574 programs under `PYSTACHY_IRCHECK=1`.
- `tools/scaling.py --check --ops -n 500,1000`, every shape, hosted and native: pass. The
  first version failed it: each close reading of a function rescanned the whole list of
  functions, so a chain of 1,000 functions that pass a constant on took 2.3 times the
  compiler lines of a chain of 500. It takes 2.0 times now.
- Lean: `check-lean-corpus` (486 programs), `check-lean-int` (138), `check-lean-storage`
  (170) and `check-lean-guards` accept.

Not run: full `make verify`, `make irsame`, macOS, ARM64, UBSan.

## Limits

- The pass removes no function itself. `PYSTACHY_AOT_OPT=0` still compiles the
  functions left without a caller.
- A field is known by its name alone, so two classes that share a field name share
  its answer.
- A dynamic `Any` field that holds `None` is not decided: its object starts with a
  null word, which is not the `None` box.
- A function whose parameters recursion passes through is read once more each time a
  parameter is lowered.
