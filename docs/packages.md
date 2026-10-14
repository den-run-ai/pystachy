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

## What gets shipped

| Deliverable | Consumer needs |
|---|---|
| Source wheel | CPython, or Pystachy + LLVM to compile its supported subset |
| AOT executable | Matching OS/architecture and system libraries; no Python, LLVM or source wheels |
| CPython extension | Existing experimental [`pystachy ext`](ffi.md#building-a-cpython-extension) scalar export contract |

Packaging does not expand the supported language or APIs. C extension imports,
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
