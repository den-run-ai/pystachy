# Selected PyPI execution checks

These checks use eleven historical cohort members that have known public imports and
pure wheels with no required runtime dependencies on the pinned interpreter; the
[wheel lock](requirements.txt) lists all eleven. Six previously stopped at an argparse
import. The other five cover changed stdlib blockers and previously accepted imports.
The argparse-addons wheel joins the original ten as a follow-up to its successful import
compilation in the broader sweep. Use the pinned CPython and a bootstrapped Pystachy
checkout. The [inventory](inventory.md) describes the separate dependency census.

### v0.2.0 measurements

| Measured stage | Before stdlib additions (`8444af96`) | After additions (`6d9b1a3c`) | With argparse (`3aa7265a`) |
|---|---:|---:|---:|
| All referenced stdlib modules emitted IR, 7,761 complete profiles from 10,000 ranks | 1,399 | 1,960 | 2,047 |
| Root-wheel imports emitted IR, 111 historical argparse-first packages | 0 | 0 | 2 |
| Root-wheel imports emitted IR, 198 attributable packages from 200 sampled | 34 | 38 | 38 |
| Installed imports matched CPython in JIT and AOT, 11 selected packages | 2 | 2 | 4 |
| API calls matched in both modes, 12 probes | 1 | 1 | 2 |
| File or CLI workflows matched in both modes, 2 probes | 0 | 0 | 1 |

Adding `ArgumentTypeError` raised the API result to 3/12. The successful file workflow
uses an unmodified Roman package. Its upstream CLI still rejected at this checkpoint.
The adapted JSON-repair CLI separately passed 13 process scenarios. The inventory
reused 7,516 same-version source profiles without original wheel hashes and rescanned
514 wheels. The eleven-package sample measures selected APIs and workflows only.

### Installed wheel execution

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
probe checks that the public import resolves inside this target. Each native IR
pass requires a nonempty file and a second compilation that rejects the exact
wheel source after a temporary syntax error.

To compare multiple compiler checkouts, use the same wheelhouse and the tool from
this checkout. Their compiled binaries must each sit beside their own runtime and
library.

The JSON separates CPython output, IR compilation, JIT execution, AOT build and AOT
execution. Each completed execution must match the CPython exit status and both
output streams. A failed CPython oracle aborts the run. An IR rejection leaves native
execution untested.

For roman, a client parses two file paths, reads a numeral, increments it and writes
a new numeral; the probe compares the output file bytes independently. Two other
cases call the unmodified upstream CLI and run all eight sdist tests. The
argparse-addons probe checks the integer converter directly and its log-level parser
separately.

Select one distribution with `--project NAME`. The timeout is per command and
defaults to 120 seconds.

## Root-wheel import compilation

Replay the [historical argparse-first cohort](argparse-first.jsonl) or the
[rank sample](rank-sample.jsonl), selected at 20 projects per 1,000 ranks.
Each row pins the wheel URL, SHA-256 and public import name. From the repository
root, use one bootstrapped checkout per compiler.

```sh
cohort=tests/upstream/pypi/argparse-first.jsonl
mkdir -p build/probe-wheels
jq -r .url "$cohort" | (cd build/probe-wheels && xargs -n 1 curl -fsSLO)
python tools/pypi_import_ir.py "$cohort" build/probe-wheels build/imports.json \
  pre=/path/to/pre-stdlib current=/path/to/current
```

Only that wheel's Python sources and the compiler's own library are visible. Resources and
third-party dependencies are absent. An IR pass also requires that replacing the target
module with invalid syntax makes the compiler reject that exact file. Missing, ambiguous and
stdlib-colliding targets are excluded. The JSON retains each compiler's outcome, first-stage
diagnostics, cohort hash and compiler identities. Package execution is measured separately above.
