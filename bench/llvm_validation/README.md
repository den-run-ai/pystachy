# Reduced LLVM checks: Linux x86-64 experiment

This record accompanies the [optional validation probe](../../docs/llvm-validation.md).
It contains correctness checks, not performance measurements. The compiler source
is unchanged from `f7103067545b43cdcd8ce20dc66b1571425b3a8d`; the measured **local** harness commit is
`e2a432801a54f9046b203b8be6e9e3251d3922b6`. Publication may preserve the exact
source bytes under a different commit SHA; the report also pins their hashes. The run used CPython 3.13.16 and LLVM
18.1.3 for generation, extraction, optimization, structural verification and native
code generation.

| Check | Observed result |
|---|---|
| LLVM structural verification | Source, intermediate passes, target and interpreter drivers accepted. Malformed return type rejected. |
| Native differential execution | All 386 inputs agree with CPython before and after optimization. Integer boundaries, subnormals, signed zero, infinity and NaN classification included. |
| Native wrong-mask control | Detected mismatches in the affected integer function. |
| llubi executed paths | All 386 inputs agree before and after optimization, 772 checked calls in total. |
| llubi controls | Wrong mask exits 86; signed-overflow poison reaching a branch exits 1 with the expected UB diagnostic. |
| Alive2 refinement | **Unavailable; not validated.** `refinement_checked` remains false. |

The [run report](linux-x86_64-2026-11-07.json) retains the exact commands, version
strings, input values, statuses, source hashes and raw artifact hashes. The
[interpreter provenance](llubi-provenance.json) retains its actual binary hash,
wrapper, build command, package versions/checksums, compatibility diff, Apache-2.0
license, and the key raw diagnostics. The full raw directory is identified there;
rerunning the command below regenerates the IR, wrappers and complete output files.
No native binaries or dependency archives are included in this repository.

## Interpreter identity and reproduction

The interpreter is the standalone upstream revision
[`a0500882b13b33d076edb80de44be680ccd972c1`](https://github.com/dtcxzyw/llvm-ub-aware-interpreter/tree/a0500882b13b33d076edb80de44be680ccd972c1),
linked against LLVM 23.1.6, with two API adaptations recorded in the provenance:
`TargetLibraryInfo::getLibFunc` uses a boolean result and output argument, and the
SCEV visitor handles `SCEVPtrToIntExpr`. The interpreter arithmetic implementation
was unchanged. This is a locally built standalone interpreter, not the official
LLVM 23 `llubi` executable. The older LLVM 18 toolchain used by Pystachy stayed
selected throughout generation and native checks.

To reproduce:

1. Build that revision against a compatible LLVM development package, applying the
   recorded API changes when using the recorded LLVM 23 package. Adapt the recorded
   build flags and shared-library search path to the local installation.
2. Use the pinned Python and LLVM 18 environment from
   [development setup](../../docs/install.md), and select the interpreter explicitly:

```sh
python3 tools/llvm_validation.py --out /tmp/pystachy-llvm-interpreted \
  --llubi /absolute/path/to/llubi
python3 -m unittest discover -s tools -p test_llvm_verification.py
```

The output directory must be new. Put the interpreter on `PATH` to include the
optional real-interpreter unit test; otherwise it skips explicitly.

The recorded focused run passed all 16 tests, including that interpreter test,
and `make lint` and `make check-repository` also passed. Full compiler/runtime
verification and an actual Alive2 invocation were not run for this tooling-only
prototype. A separate optional aggregate discovery (`test_*verif*.py`) showed
nine failure markers before interruption, without a final traceback summary; this
incomplete run is **not** a passing suite. Applicable CI remains a separate
publication gate.

A passing interpreter run applies to these inputs and the UB classes implemented
by this particular interpreter. It does not establish all-input equivalence or
validate Pystachy's general exception, allocation, pointer or aliasing behavior.
