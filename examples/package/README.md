# One package, two runtimes

From the checkout root, with [Pystachy installed](../../docs/install.md) and uv:

```sh
uv build ports -o dist
uv build examples/package -o dist
uv pip install --no-index --find-links dist --target build/deps pystachy-demo==0.1.0
PYTHONPATH=build/deps python3 examples/package/use.py
PYSTACHY_PATH=build/deps pystachy run examples/package/use.py
PYSTACHY_PATH=build/deps pystachy build examples/package/use.py -o build/chapter
build/chapter
```

Each run prints `Chapter IV`. `use.py` imports the installed `pystachy_demo`
library, which imports the installed Roman-numeral port. Its `pyproject.toml`
declares that dependency and a CPython console command, `pystachy-demo`.
To compile the installed CLI, use `build/deps/bin/pystachy-demo` as the input file;
the compiler accepts Python source without a `.py` suffix.

Share the wheels in `dist/`; see [packages](../../docs/packages.md) for locked
installs and deployment. The example versions are local teaching artifacts;
these commands do not publish anything.
