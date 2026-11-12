# Optional mypyc component qualification

These ten original tests exercise mypyc's `NameGenerator` in isolation through
the [generated pytest runner](../../docs/pytest-native.md). They use an unchanged
upstream module with concrete types; no dynamic `Any`, compiler changes or mypyc
package installation is needed. This does **not** qualify the full mypy/mypyc
package, its build pipeline or its upstream test suite.

The dependency is downloaded separately rather than vendored here:

| Source | Pinned value |
|---|---|
| Repository | `python/mypy` |
| Commit | `1231cf158a9cab0c41f613f3d8070c1332632f29` |
| Path | `mypyc/namegen.py` |
| Git blob | `1e05531021752709fbc0144d33ddf8377fa1dfed` |
| SHA-256 | `739a7bcb1c54c96a8944da8a9a4542475c56d2ee392db22ba933e74749fe23ae` |

From the repository root, fetch the exact source and verify its bytes before
writing it. The upstream source retains the repository's
[MIT license](https://github.com/python/mypy/blob/1231cf158a9cab0c41f613f3d8070c1332632f29/LICENSE).

```sh
python3 - <<'PY'
import hashlib
from pathlib import Path
from urllib.request import urlopen

commit = "1231cf158a9cab0c41f613f3d8070c1332632f29"
base = f"https://raw.githubusercontent.com/python/mypy/{commit}"
source = urlopen(f"{base}/mypyc/namegen.py", timeout=30).read()
expected = "739a7bcb1c54c96a8944da8a9a4542475c56d2ee392db22ba933e74749fe23ae"
if hashlib.sha256(source).hexdigest() != expected:
    raise SystemExit("namegen.py source hash mismatch")
destination = Path("build/pytest-mypyc-source/namegen.py")
destination.parent.mkdir(parents=True, exist_ok=True)
destination.with_name("LICENSE.mypy").write_bytes(urlopen(f"{base}/LICENSE", timeout=30).read())
destination.write_bytes(source)
PY
```

Use the pinned development Python/pytest environment and working LLVM toolchain
described in [installation](../../docs/install.md). Run generated CPython first,
then native AOT; both commands compare every case and phase against real pytest:

```sh
PYTHONPATH="$PWD/build/pytest-mypyc-source" PYSTACHY_PATH="$PWD/build/pytest-mypyc-source" \
  python3 tools/pytest_native.py examples/pytest_native_mypyc --mode python --compare \
  --work-dir build/pytest-native-mypyc-python --json build/pytest-native-mypyc-python.json
PYTHONPATH="$PWD/build/pytest-mypyc-source" PYSTACHY_PATH="$PWD/build/pytest-mypyc-source" \
  python3 tools/pytest_native.py examples/pytest_native_mypyc --mode aot --compare \
  --work-dir build/pytest-native-mypyc-aot --json build/pytest-native-mypyc-aot.json
```

The cases cover name escaping, unique module prefixes, cached translations,
unknown modules, global names, missing-module errors and separate compilation.
They passed under generated CPython and native AOT with CPython 3.13.16,
pytest 9.2.0 and LLVM 18. This optional check performs no automatic download
during normal example tests or CI.

Upstream's own `test_namegen.py` uses `unittest.TestCase`. The separate
[upstream qualification](../../tests/upstream/pytest/README.md)
runs all five of its original methods in real unittest, exports them with an
explicit method-to-pytest mapping, then checks adapted pytest, generated CPython,
native JIT and native AOT. Run it with:

```sh
python3 tools/pytest_native_upstream.py --suite mypyc-namegen --fetch \
  --compiler ./pystachy --json build/pytest-upstream-mypyc.json
```

The upstream module, tests, package initializers and MIT license are hash-pinned.
Those five upstream methods are distinct from the ten original cases above;
neither suite qualifies the complete mypy/mypyc package.
