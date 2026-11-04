# Selected PyPI execution checks

Use the pinned CPython and a bootstrapped Pystachy checkout. These eleven historical
cohort members have known public imports and pure wheels with no required runtime
dependencies on the pinned interpreter. Six previously stopped at an argparse
import. The other five cover changed stdlib blockers and previously accepted
imports. The argparse-addons wheel joins the original ten as a follow-up to its
successful import compilation in the broader sweep. The [inventory](inventory.md)
gives the complete cohort and the separate dependency census. This purposive sample cannot estimate a population pass rate.

Download the exact wheels once and retain the original roman sdist for its tests.

```sh
mkdir -p build/probe-wheels
python -m pip download --only-binary=:all: --require-hashes \
  -r tests/upstream/pypi/requirements.txt -d build/probe-wheels
curl -fL https://files.pythonhosted.org/packages/source/r/roman/roman-5.2.tar.gz \
  -o build/probe-wheels/roman-5.2.tar.gz
python tools/pypi_workflows.py build/probe-wheels --compiler ./pystachy \
  --output build/pypi-workflows.json
```

Each wheel is hash-checked and installed offline by uv into its own empty target,
including package resources. CPython runs with site-packages disabled, and the
probe checks that the public import resolves inside this target. Use the same
wheelhouse and the tool from this checkout to compare multiple compiler checkouts.
Their compiled binaries must each sit beside their own runtime and library.

The JSON separates CPython output, IR compilation, JIT execution, AOT build and
AOT execution. Each completed execution must match the CPython exit status and
both output streams. For roman, a client parses two file paths, reads a numeral,
increments it and writes a new numeral. The probe compares the output file bytes
independently. Two other cases call the unmodified upstream CLI and run all eight
sdist tests. The argparse-addons probe checks the integer converter directly and
its log-level parser separately. Select one distribution with `--project NAME`.
A failed CPython oracle aborts the run. An IR rejection leaves native execution
untested. The timeout is per command and defaults to 120 seconds.

## Root-wheel import compilation

Replay either the historical argparse-first cohort or the rank sample in the census evidence
with its JSONL manifest and local wheelhouse. Each row pins a rank, project, version, wheel
filename, SHA-256 and public import name. Use one bootstrapped checkout per compiler.

```sh
python tools/pypi_import_ir.py cohort.jsonl wheels results.json \
  pre=/path/to/pre-stdlib current=/path/to/current
```

Only that wheel's Python sources and the compiler's own library are visible. Resources and
third-party dependencies are absent. An IR pass also requires that replacing the target
module with invalid syntax makes the compiler reject that exact file. Missing, ambiguous and
stdlib-colliding targets are excluded. The JSON retains each compiler's outcome, first-stage
diagnostics, cohort hash and compiler identities. Package execution is measured separately above.
