# Reduced LLVM optimization checks

`tools/llvm_validation.py` is an optional Linux developer probe. It emits LLVM
with the **current hosted Pystachy compiler**, extracts three scalar functions
using `llvm-extract`, and checks an intraprocedural optimization pipeline. It
changes no compiler defaults and needs no runtime or compiler bootstrap.

```sh
python3 tools/llvm_validation.py --out /tmp/pystachy-llvm-check
python3 tools/llvm_validation.py --out /tmp/pystachy-llvm-alive \
  --alive-tv /path/to/alive-tv --require-alive2
python3 tools/llvm_validation.py --out /tmp/pystachy-llvm-interpreted \
  --llubi /path/to/llubi
```

The output directory must be new. Use the pinned Python and matching LLVM tools
from [development setup](install.md); `PYSTACHY_LLVM` selects their directory,
otherwise the tool searches `PATH`. Each subprocess has a 60-second timeout.
`--timeout` changes that per-command bound, not the meaning of a timeout.

## What runs

| Kernel | Lowering and finite inputs |
|---|---|
| `(a + b) & 65535` | The emitted signed-overflow intrinsic and masked result; 121 input pairs including both signed 64-bit limits and sums outside that range. |
| Signed minimum | Comparisons, branches, stack slots and their simplification; 121 pairs including signed limits. |
| `a * 1.25 + b` | Floating multiplication and addition; 144 pairs including subnormals, signed zero, infinities and NaNs. |

The extracted functions retain their bodies and intrinsic declarations. Extraction
promotes their internal linkage to hidden linkage so a small C wrapper can call
them. No overflow checks, flags or exception paths are deleted by the harness.
These three functions have no Pystachy runtime calls; general exception/GC/pointer
and aliasing behavior remains outside this probe.

The default passes are `mem2reg,instcombine,simplifycfg`. `--passes` accepts a
comma-separated list of function passes and wraps it in `function(...)`; module
pipelines are excluded. LLVM verifies the source, each pass and the output.
The source and optimized modules are then compiled at `-O0 -ffp-contract=off`
and called in separate processes. Both result sets must agree with the CPython
execution of the same kernel definitions. Native execution still uses LLVM's
backend; it is not an independent interpreter of LLVM semantics.

Integer results and non-NaN double bits must match exactly, including the sign of
zero. NaNs compare by `isnan`, without a payload/sign promise. Missing functions,
missing result rows, subprocess failures and timeouts fail the check.

A valid module with a deliberately wrong mask must produce native mismatches; a
malformed return type must be rejected by LLVM. These controls guard against
empty or nonexecuted checks passing.

## Optional Alive2

When `alive-tv` is supplied or on `PATH`, the tool compares the extracted source
and optimized target. Every selected function must exist on both sides, and its
summary must report exactly three correct transformations, zero incorrect,
zero failed-to-prove and zero errors. The intentionally wrong mask must also
produce a complete counterexample result. Exit code alone is insufficient:
[Alive2's driver](https://github.com/AliveToolkit/alive2/blob/master/tools/alive-tv.cpp)
can return zero with incorrect transformations and ignores functions missing
from one input. An unknown or incomplete output format is inconclusive.

Use a compatible Alive2/LLVM build. [Upstream's build guidance](https://github.com/AliveToolkit/alive2#building-and-running-alive2)
targets LLVM main; an arbitrary current binary is not guaranteed to parse or
validate LLVM 18 output. Alive2 does not support interprocedural transformations.
The probe does not download a solver, build Alive2 or silently replace LLVM.

## Optional UB-aware interpretation

`--llubi` appends a bounded LLVM `main(argc, argv)` driver to each reduced module.
It calls the three functions on the same 386 inputs and branches on every result
comparison, consuming returned poison. LLVM first verifies the driver, then the
interpreter runs it with `--max-steps=100000` and the same wall-clock timeout.
The source and optimized modules must exit successfully without diagnostics; the
wrong mask must return the driver's dedicated mismatch code. A separate, valid
LLVM control uses `add nsw i8 127, 1` and must diagnose **Branch on poison** when
its result reaches a branch. Parse errors, unsupported instructions, step limits,
other failures and timeouts cannot satisfy this control.

The [llubi documentation](https://llvm.org/docs/CommandGuide/llubi.html) describes
an LLVM interpreter that detects UB on **executed paths**. This probe does not use
its reduction mode or accept invalid IR. Successful interpretation records
`llubi.status: checked_paths`, with two modules and 386 cases per module. It does
not establish refinement, all-input correctness, or absence of every LLVM UB
class. The [standalone interpreter's limitations](https://github.com/dtcxzyw/llvm-ub-aware-interpreter#limitations)
include incomplete treatment of undef, aliasing and some memory effects.

Use an interpreter compatible with the emitted IR. The recorded experiment used
a pinned standalone revision linked against LLVM 23, with two build API
adaptations; it was **not** an official LLVM release binary. See the
[experiment record](../bench/llvm_validation/README.md) for source, package and
binary identities. The probe does not provision or patch the interpreter. A
supplied interpreter that is unavailable or cannot complete its checks returns
exit 2, while recording native results separately.

## Reports and test coverage

`report.json` separates LLVM structural validity, finite native agreement,
optional interpreter path checks, and `refinement_checked`. When Alive2 is missing, native checks can finish with exit
zero and `refinement_checked: false`; this establishes **no formal validation**.
`--require-alive2` returns exit 2 unless refinement and the counterexample control
complete. A supplied checker that fails or is inconclusive also returns exit 2.
Required LLVM/native checks that fail return exit 1. Invalid CLI arguments return
exit 2.

The directory retains the emitted/extracted/transformed modules, source kernels,
wrapper, expected results, every command's stdout/stderr, tool versions, compiler
source hashes and artifact hashes. Preserve it when investigating a failure.
These reduced checks supplement [CPython differential tests](testing.md); neither
LLVM's structural verifier nor finite native agreement proves absence of UB,
correctness for every input, or correctness of the full compiler/runtime.

The focused tests run in the existing Lint `test_*verif*.py` discovery:

```sh
python3 -m unittest discover -s tools -p test_llvm_verification.py
```

They cover fail-closed result parsing plus real LLVM/native execution when the
matching tools are installed; an optional test also executes `llubi` from `PATH`.
The optional Alive2 protocol tests use synthetic summaries; an unavailable Alive2 executable is never described as tested.
