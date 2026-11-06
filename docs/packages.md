# Share packages and apps

Install the compiler as in [installation](install.md). Ship libraries as ordinary
Python **source wheels**: `.py` modules/packages with `pyproject.toml` metadata.
Use uv or pip for building, version constraints, dependency resolution and installation;
Pystachy compiles the installed sources together with the app. There is no additional
package format, registry, native library ABI or resolver.

## Small working example

The [package tutorial](../examples/package/README.md) builds a reusable library
and CLI depending on the [adapted ports](../ports/README.md). Its complete metadata
is in [pyproject.toml](../examples/package/pyproject.toml): standard `[build-system]`,
`[project]` dependencies and `[project.scripts]`. Share the resulting wheel and sdist
through an existing package index or a wheel directory. Choose your own distribution
and import names when copying the example.

Install into a **dedicated directory**, then point both runtimes at the same code:

```sh
uv pip install --target build/deps path/to/library.whl
PYSTACHY_PATH=build/deps pystachy build app.py -o app
PYTHONPATH=build/deps python3 app.py
```

`python3 -m pip install --target build/deps path/to/library.whl` also works.
For development without a wheel, point `PYSTACHY_PATH` / `PYTHONPATH` at your
package's `src/` directory. Ordinary non-editable installs are the supported path;
Pystachy does not execute `.pth` files or editable import hooks and does not search
a CPython virtual environment automatically.

## Lock an app's dependencies

Put direct version requirements in `requirements.in` (or use `pyproject.toml` as
the compile input). Resolve **all** dependencies once and commit `requirements.txt`:

```sh
uv pip compile requirements.in --generate-hashes -o requirements.txt
uv pip sync --target build/deps --require-hashes requirements.txt
PYSTACHY_PATH=build/deps pystachy build app.py -o app
```

For a private/local wheel directory, add `--no-index --find-links dist` to both uv
commands. Use immutable versioned wheels, rather than editable/directory/Git inputs,
for hashed installs. `sync` removes unlisted packages; reserve `build/deps` for
this app. Libraries declare compatible dependency ranges; apps lock exact versions.
Record the Pystachy release/commit and LLVM toolchain alongside the lockfile.

## Install native JSON repair into CPython

The optional companion wheel packages the [schema-free repair example](../examples/json_repair/)
as `pystachy_json_repair` and installs its AOT executable as `json-repair-native`.
The distinct names let an application also install upstream `json-repair` for schema or file APIs.

Build on a native glibc Linux x86-64 or aarch64 host, using GIL-enabled CPython 3.12+
with `venv`/`ensurepip`, GNU `readelf` (binutils), Pystachy's LLVM prerequisites and
the pinned [packaging tools](../tools/requirements-packaging.txt). The builder runs
the source compiler under Python. PyPy, free-threaded CPython, other architectures,
cross-compilation and macOS are unsupported by this builder; the current extension
linker targets Linux.

```sh
python -m pip install -r tools/requirements-packaging.txt
python tools/build_json_repair_wheel.py --out build/json-repair-wheel
python -m pip install ./build/json-repair-wheel/*.whl
python -I -c 'from pystachy_json_repair import loads; print(loads("{answer:42,}"))'
printf '%s' '{answer:42,}' | json-repair-native
python -I tests/upstream/json_repair/extension.py
```

The builder checks both binaries' ELF architectures and uses the host tag
`cp312-abi3-linux_x86_64` or `cp312-abi3-linux_aarch64`. These are local platform
wheels. Required glibc symbol versions and system libraries depend on the build
environment; the ELF report is a diagnostic, not a manylinux certification or a
guarantee of compatibility with every system of that architecture. It is retained
as `native-abi.json` in the wheel's `.dist-info` directory and in the adjacent
`.validation.json` report, which also records the wheel hash and test results.

Before publishing a wheel into the output directory, the builder installs it
offline into a temporary virtual environment outside the checkout. It checks the
real extension and its installed file hashes, replays the complete maintained API
corpus normally and with forced GC, and runs the CLI cases with an empty `PATH`.
The checks cover stdin, files and preservation of destinations on errors. They also
verify two independent spawned process workers and rejection of native calls from
a thread other than the importing thread. A failed check leaves any previous wheel
unchanged. To repeat the check on another compatible host or CPython version:

```sh
python tools/json_repair_wheel_smoke.py ./build/json-repair-wheel/*.whl --json wheel-check.json
```

The [2026-11-06 evaluation](../bench/json_repair/results/installed-api-2026-11-06.md)
validates the same Linux x86-64 wheel on CPython 3.12.14 and 3.13.16, including all
837 API cases in normal and forced-GC modes, 20 CLI cases, spawned workers and
foreign-thread rejection. Its required glibc symbol floor is 2.38; it was run on
glibc 2.39. The aarch64 build and
tag selection are supported, but an ARM wheel still needs this validation on an ARM
host before distribution. The wheel contains the two compiled binaries and their
licenses. The executable runs without Python or LLVM. Calls from CPython retain
the [extension threading contract](ffi.md#threading-and-host-lifetime); use process
workers that each import the module for parallel repair.

## What gets shipped

| Deliverable | Consumer needs |
|---|---|
| Source wheel | CPython, or Pystachy + LLVM to compile its supported subset |
| AOT executable | Matching OS/architecture and system libraries; no Python, LLVM or source wheels |
| CPython extension | Existing experimental [`pystachy ext`](ffi.md#building-a-cpython-extension) scalar export contract |

Packaging does not expand the [supported language](language.md#support-at-a-glance) or APIs. C extension imports,
dynamic import hooks and arbitrary PyPI dependencies are not supported by native
compilation. Wheels must contain the `.py` sources; a platform wheel is not evidence
of compatibility. Test the public API under CPython and Pystachy JIT/AOT.
Runtime data files and external commands/libraries must be shipped separately;
AOT does not embed package resources. Existing [AskMe-mini](../examples/agent/README.md)
and [router](../examples/route/README.md) examples show standalone apps.

The ports wheel preserves upstream import names and ships the adapted sources,
licenses and port notes. Keep it separate from installations of the corresponding
upstream distributions, whose files would overlap. Bundled standard-library ports
remain part of the compiler installation.

References: [Python package metadata](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/),
[uv build](https://docs.astral.sh/uv/guides/package/),
[uv locking and sync](https://docs.astral.sh/uv/pip/compile/).
