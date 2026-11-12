# JSON repair from CPython

The companion module calls the [json_repair port](../../ports/json_repair/PORT.md)'s
schema-free repair from a normal CPython application. It has its own import name, so an
application can also install upstream `json_repair` for schema and file-wrapper APIs.

Build from the repository root on Linux with a built compiler, LLVM and
GIL-enabled CPython 3.12 or later.

```sh
mkdir -p build/json_repair/pystachy_json_repair
cp examples/json_repair/pystachy_json_repair/__init__.py build/json_repair/pystachy_json_repair/
PYSTACHY_PATH=ports ./pystachy ext examples/json_repair/_native.py \
    -o build/json_repair/pystachy_json_repair/_native.abi3.so

PYTHONPATH=build/json_repair python3.13 - <<'PY'
import pystachy_json_repair as repair

text = '{name:"café", items:[true, null,],}'
print(repair.repair_json(text, ensure_ascii=False))
value, events = repair.loads(text, logging=True)
assert value == {"name": "café", "items": [True, None]}
PY
```

`repair_json` returns JSON text by default, including the port's empty-string
sentinel. `loads` and `return_objects=True` return Python objects. Valid inputs
to object-return calls use CPython's decoder directly unless `skip_json_loads`
is set. Malformed inputs are repaired natively. Object and log results cross the
extension boundary as JSON text, which the companion decodes in CPython.

Unquoted multilingual keys and values follow the upstream repair rules:
`loads('{界:1}')` returns `{'界': 1}` and `loads('[é]')` returns `['é']`.
The native parser uses CPython 3.13's Unicode 15.1 character classes. Malformed
numbers, punctuation and emoji still follow upstream's bounded heuristics.

The native integer parser uses CPython’s default limit of 4,300 decimal digits.
If the host changes `sys.set_int_max_str_digits()`, large numbers can produce
different results or a `ValueError` when CPython decodes a native result.

The native calls follow the [extension thread and GIL contract](../../docs/ffi.md#threading-and-host-lifetime).

Check the built module against all 962 [recorded API cases](../../tests/upstream/json_repair/README.md).
The verifier checks the loaded extension and reuses the same corpus and comparison
as the standalone replay. Omit the directory to verify an installed package.

```sh
python3.13 -I tests/upstream/json_repair/extension.py build/json_repair
PYSTACHY_GC_STRESS=1 python3.13 -I tests/upstream/json_repair/extension.py build/json_repair
```

To install the companion and command into a virtual environment, [build a local wheel](../../docs/packages.md#install-native-json-repair-into-cpython).

For use without a Python interpreter, build the [file and pipe command](../../ports/json_repair/PORT.md#file-and-pipe-command).
