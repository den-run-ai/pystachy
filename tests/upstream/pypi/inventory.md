# Top-PyPI inventory

Resolve a dated ranking once. Keep the ranking, release manifest, source profiles and
comparison JSON together. Resolving the ranking again selects the then-current releases.
A manifest pins each eligible wheel's filename, size, URL and SHA-256.

```sh
mkdir -p build/pypi
cd build/pypi
curl -fLO https://raw.githubusercontent.com/hugovk/top-pypi-packages/29c0d4c38c28c0e6b99e73fa09cb91a2323ca51b/top-pypi-packages-30-days.min.json
echo '3e958a64ebe1de0b6a4ab4c6b465d481f350fd1dfa926c639add36eb34dabc1e  top-pypi-packages-30-days.min.json' | sha256sum -c -
cd ../..
python tools/pypi_inventory.py resolve build/pypi/top-pypi-packages-30-days.min.json build/pypi/releases.json -j 8
python tools/pypi_inventory.py scan build/pypi/releases.json build/pypi/profiles.json --limit 100
python tools/pypi_inventory.py compare build/pypi/profiles.json build/pypi/comparison.json /path/to/before/pystachy /path/to/after/pystachy
```

Use pinned CPython. The default cutoff for `resolve` and `scan` is rank 10,000.
The scan accepts a manifest subset for selected ranks and `--wheel-dir` for a local
wheel cache. It verifies bytes before parsing. Non-yanked Python 3 pure wheels
up to 50 MB qualify. `no-eligible-pure-wheel` means the release has a non-yanked
wheel, but none carries both a `py3*` interpreter tag and the `none-any` tags.
It includes platform-specific wheels and Python 2 pure wheels. Separate statuses
cover sdist-only releases, missing projects, oversized files and failed fetches
or integrity checks. The manifest retains `requires_python` for interpreter checks.

The recovered probe scans module-level imports across the wheel's Python sources.
It skips tests, optional import fallbacks, type-checking suites, local functions
and files larger than 3 MB. A partial parse, no usable source and a successfully
parsed module with zero stdlib imports have distinct records. Imported names
(`from pathlib import Path`) resolve to their longest known CPython module prefix.
This estimates demand only. Conditional imports can be inactive, and individual
APIs or third-party dependencies can still fail.

`compare` also accepts archived `[{rank, project, stdlib}, ...]` records. It measures
each required module's bare `import` once on each compiler, with the compiler's own
shipped library and no overlay, then records unresolved modules per project.
Both sides use the same CPython module universe. Diagnostics, timeout, compiler
hashes and source revisions accompany the rows.

For archived profiles, join the companion feature census by exact
`(rank, project)`. Its `files` count is the number of parsed files and `unparsable`
counts file-read or parse failures under the same path and 3 MB size filters.
Keep the dotted imports from the import census. Supply those counts as `parsed`
and `skipped` in the comparison input. The archive omits counts of files over
the size limit and wheel digests.

Of 395 historical rows with no recorded module requirement, 163 had parsed Python
source, 231 had no eligible source, and one had only unparsable source. Only the
163 observed empty profiles qualify for the dependency score. Keep partially
parsed profiles separate when reporting complete profiles.
[Selected package execution checks](README.md) measure
actual import, API and workflow behavior separately.
