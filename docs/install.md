# Installation

Choose a native release package, the Docker image, or a source build.
Native packages need **LLVM 18 on Linux / LLVM 20 on macOS** to compile programs;
the Docker image includes LLVM. Neither requires Python to run the compiler.

## Native release packages

Download the matching archive and `SHA256SUMS` from
[GitHub Releases](https://github.com/den-run-ai/pystachy/releases).

| Package target | Requirements |
|---|---|
| `linux-x86_64` | Ubuntu 24.04 or compatible Linux with glibc 2.39+, LLVM 18 |
| `macos-arm64` | Apple Silicon, macOS 15+, Xcode Command Line Tools, LLVM 20 |
| `macos-x86_64` | Intel, macOS 15+, Xcode Command Line Tools, LLVM 20 |

Install the toolchain once:

```sh
# Ubuntu
sudo apt update
sudo apt install clang-18 llvm-18 llvm-18-runtime

# macOS
brew install llvm@20
```

Check the downloaded archive's entry in `SHA256SUMS` (`sha256sum` on Linux,
`shasum -a 256` on macOS), then extract it. For example, with a Linux archive:

```sh
tar -xzf pystachy-VERSION-linux-x86_64.tar.gz
mkdir -p "$HOME/.local/bin"
mv pystachy-VERSION-linux-x86_64 "$HOME/.local/pystachy-VERSION"
ln -sfn "$HOME/.local/pystachy-VERSION/bin/pystachy" "$HOME/.local/bin/pystachy"
export PATH="$HOME/.local/bin:$PATH"
pystachy run demo.py
```

Replace `VERSION` with the release tag, such as `v0.1.0-alpha.1`, and use your
platform's archive name. Keep the complete extracted directory: it contains the
runtime and libraries alongside the compiler. The directory can be moved, and its
launcher resolves symlinks. `manifest.json` records the source commit and file hashes.
Check the installed release and commit with `pystachy --version` or `pystachy -V`;
this command works without LLVM or Python.

## Docker

The image runs on **Linux amd64**, including Docker Desktop on Intel hosts.
Apple Silicon can use `--platform linux/amd64` with Docker's emulation; there is
currently no native Linux arm64 release image. Use the image name and version from
the release notes:

```sh
IMAGE=DOCKERHUB_NAMESPACE/pystachy:VERSION
docker run --rm "$IMAGE" --version
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" "$IMAGE" run demo.py
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" "$IMAGE" build demo.py -o demo
```

The generated executable targets Linux, even on Docker Desktop. Run it in the image
when your host is macOS:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" --entrypoint /work/demo "$IMAGE"
```

The image includes LLVM 18, the native compiler and its libraries; runtime caches go
to `/tmp` unless `PYSTACHY_CACHE` is overridden. Release tags identify a tested source
commit. `latest` advances only for stable releases; prereleases use explicit version tags.

## Build from source

Source builds need **Python 3.11+** to bootstrap and `make`, in addition to LLVM.
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
