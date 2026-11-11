# Generated native test examples

These original pytest-style tests exercise current stdlib APIs, the iniconfig and
jdcal ports, typed fixtures and opt-in dynamic payloads. They demonstrate the
[bounded runner](../../docs/pytest-native.md), not full pytest or upstream-suite support.

From the repository root, with the pinned development environment and LLVM:

```sh
PYTHONPATH=ports PYSTACHY_PATH=ports python3 tools/pytest_native.py \
  examples/pytest_native --mode jit --compare
PYTHONPATH=ports PYSTACHY_PATH=ports python3 tools/pytest_native.py \
  examples/pytest_native --mode aot --compare
python3 examples/pytest_native/benchmark.py --samples 5 --json build/pytest-benchmark.json
```

`test_dynamic.py` deliberately opts in to dynamic `Any`; the other modules and
the runner do not. Its tests verify aliasing, shared mutations and fresh fixture
values between tests. Numeric identity tracking still follows the compiler's
normal import/boundary policy when these modules are compiled together.

## Illustrative execution measurements

The [five-case benchmark and reproduction instructions](results/README.md) compare
original pytest, generated CPython and prebuilt native execution. All timed samples
match the original phase outcomes. Build costs are reported separately; these
small-suite numbers are not general pytest speedups.
