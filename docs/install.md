# Installation

Pystachy needs **LLVM 18 on Linux / LLVM 20 on macOS**, **Python 3.11+** to bootstrap, and `make`.
There are no pip dependencies for building or running the compiler. Ordinary AOT programs
run without Python; compiling new programs still requires LLVM.

## Ubuntu 24.04

```sh
sudo apt update
sudo apt install git make python3 clang-18 llvm-18 llvm-18-runtime
git clone https://github.com/den-run-ai/pystachy
cd pystachy
make
make install
```

## macOS

On macOS 14 or later, install [Homebrew](https://brew.sh) and the Xcode Command Line Tools first
(`xcode-select --install` if they are missing). Then:

```sh
brew install llvm@20 python@3.13
git clone https://github.com/den-run-ai/pystachy
cd pystachy
make
make install
```

Homebrew's LLVM 20 is keg-only. Pystachy discovers its standard Intel and Apple Silicon
locations automatically, as well as Ubuntu's versioned toolchain. For a custom Homebrew
prefix, use `export PYSTACHY_LLVM="$(brew --prefix llvm@20)/bin"`.
`make` prefers `python3.13` when available, then `python3`; `make PY=/path/to/python`
selects a different bootstrap interpreter.

LLVM 20 supplies the Apple Silicon JIT's compact unwind registration; LLVM 18 remains
the Linux toolchain used by full verification.

The installation CI checks bootstrap, ordinary JIT/AOT, exceptions, files and garbage
collection on Linux and both macOS architectures. The full verification suite and
experimental CPython extension/embedding support remain Linux-focused; see
[testing](testing.md) and [FFI](ffi.md).

## Run a program

`make` verifies that the self-compiled compiler and runtime reach a byte-identical IR
fixed point. `make install` puts the compiler in `~/.local/bin` and its runtime and
libraries in `~/.local/libexec/pystachy`. Add the command directory to your shell's `PATH`
once if needed (in `~/.bashrc` on Linux or `~/.zshrc` on macOS):

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Save this as `demo.py`:

```python
def squares(n: int) -> int:
    return sum(i * i for i in range(n))


print(squares(1000))
```

```sh
python3 demo.py
pystachy run demo.py
pystachy build demo.py -o demo
./demo
```

Each prints `332833500`. You can also skip installation and use `./pystachy` from the
checkout. Before bootstrapping, use `python3 -m pystachy run demo.py` with Python 3.11+
on Ubuntu, or `python3.13 -m pystachy run demo.py` with Homebrew, to run the compiler
under CPython. [Compiler commands and settings](internals.md) covers other modes.

## Check or prepare dependencies

```sh
tools/setup.sh --check       # validate Python, make and all five supported LLVM tools; no installation
tools/setup.sh --minimal     # install missing build dependencies with apt/Homebrew
```

An explicit `PYSTACHY_LLVM` takes precedence over discovery; it must point to a complete
platform's LLVM `bin` directory. Set it to an empty string to explicitly select `PATH`.
If no standard installation exists, Pystachy uses the unversioned
`clang`, `opt`, `lli`, `llvm-link` and `llvm-as` on `PATH`.

On other Linux distributions, install LLVM 18, Python 3.11+ and `make` using the system
package manager, then run `tools/setup.sh --check`. The script does not configure package
repositories or replace the system Python.

## Python and development tools with uv

If your system Python is too old, [uv](https://docs.astral.sh/uv/getting-started/installation/)
can supply Python without changing it:

```sh
uv python install 3.13
uv run --no-project --python 3.13 make
uv run --no-project --python 3.13 make install
```

For development, use a virtual environment instead of installing pip packages into the
system Python. CI's Python version is pinned in `.python-version`:

```sh
uv venv --python "$(cat .python-version)"
uv pip install --python .venv/bin/python -r tools/requirements-dev.txt
tools/setup.sh --verify      # Ubuntu: also install the UBSan runtime for make verify
make lint PY="$PWD/.venv/bin/python"
make verify PY="$PWD/.venv/bin/python"
```

`make verify` uses Python 3.13 and Linux x86-64. The extra pip packages and sanitizer
runtime are for development and verification, rather than ordinary installation.

## Custom and staged installations

```sh
make install prefix=/opt/pystachy
make install prefix=/usr/local DESTDIR=/tmp/pystachy-package
make uninstall              # removes the default ~/.local installation
```

Choose a writable prefix or use an appropriate package-building environment. `DESTDIR`
stages the files while the launcher retains the final prefix, for system packaging.
Use the same `prefix` and `DESTDIR` when uninstalling a custom or staged installation.

Installed compilers cache runtime builds in `${XDG_CACHE_HOME:-$HOME/.cache}/pystachy`;
their installation directory can be read-only. `PYSTACHY_CACHE` overrides the cache path
and `PYSTACHY_HOME` overrides the resource directory. Checkout builds keep their existing
`build/` cache. Uninstallation leaves user caches and unrelated commands intact.
