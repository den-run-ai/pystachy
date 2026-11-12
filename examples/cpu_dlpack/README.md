# CPU DLPack bridge prototype

`tools/pystachy_dlpack.py` adds one optional CPython host helper,
`from_dlpack_f64(producer)`, on top of the retained `pyobj.Buffer` prototype.
Its first consumer scores a batch supplied by an object that implements only
DLPack. The helper uses NumPy >= 2.1 to own the imported tensor and expose a
CPython buffer; Pystachy reads the batch with the existing native dot loop.
No compiler, runtime ABI or C integration is added.

## Use the adapter

Put the checkout's `tools/` on the host's `PYTHONPATH`. In a CPython host module:

```python
from pystachy_dlpack import from_dlpack_f64

data = from_dlpack_f64(existing_producer)
```

Compiled code acquires `import_module("host_batches").attr("data").buffer_f64()`
and closes its `Object` and `Buffer` handles as documented in
[FFI](../../docs/ffi.md#retained-cpu-buffer-prototype). The complete consumer in
[dlpack_score.py](dlpack_score.py) exports `retain()`, `score()` and `release()`;
`retain()` replaces the previous batch. `score()` requires a successful retain.
[dlpack_host.py](dlpack_host.py) supplies the example batch and lifetime checks.
NumPy runs only in the CPython host; this does not compile NumPy or implement a
general ndarray library.

| Boundary | Contract |
|---|---|
| Device | `__dlpack_device__()` must return `(1, 0)`, DLPack CPU device 0. Reject before requesting a capsule; no device transfer. |
| Type and layout | One-dimensional native float64 with a contiguous buffer export. Reject dtype changes, flattening and noncontiguous inputs. Empty arrays, singleton arrays and contiguous offset slices work. |
| Copying | Call `numpy.from_dlpack(..., copy=False)`; no fallback copy or cast. The included producer is checked with pointer equality, `shares_memory` and visible host writes. |
| Permission | Return a read-only NumPy view and acquire a read-only `Buffer`. Other aliases can still write; callers must synchronize writers. |
| Ownership | Retained `Py_buffer` owns the NumPy view; NumPy owns the DLPack tensor and calls its deleter on final release. A Python producer wrapper need not stay alive if its allocation is retained correctly. |
| Consumption | Accept producer objects with `__dlpack__` and `__dlpack_device__`. NumPy validates capsules and rejects a second consumption of the same capsule. Each import requests a separate lease. |

Layout checks happen after NumPy consumes the capsule. A rejected layout can
therefore still consume a one-shot producer; request a fresh capsule for another
import. The adapter accepts trusted in-process producers under their DLPack
ownership contract. It inherits `Buffer`'s size limits, explicit/deferred release rules,
GIL behavior and extension owner-thread restriction.

GPU memory, asynchronous work, cross-process sharing, multidimensional arrays,
writable imports, Arrow, and exporting a Pystachy buffer as DLPack are outside
this prototype. Derived Pystachy views may use the existing checked
positive/negative strides after a contiguous root has been acquired.

## Reproduce

Use the repository's pinned Python/LLVM setup and build the native compiler.
NumPy is an optional dependency of this adapter, not a Pystachy dependency.
The example runner currently requires Linux CPython >= 3.12 with shared
`libpython`; it derives the embedding paths from its own interpreter. It clears
inherited `PYSTACHY_*` settings except `PYSTACHY_LLVM`, supplies its own cache
and GC settings, and limits each subprocess to 180 seconds.

```sh
make
python3.13 -m venv build/dlpack-venv
build/dlpack-venv/bin/python -m pip install numpy==2.3.5
build/dlpack-venv/bin/python -m unittest discover -s tools -p test_runtime_dlpack.py -v
build/dlpack-venv/bin/python examples/cpu_dlpack/check.py --compiler ./pystachy
```

The protocol unit tests run under Lint's existing `test_runtime_*.py` discovery.
Without NumPy, the two dependency/device tests run and the eight NumPy tests
explicitly skip.

The optional native runner must be invoked separately: it checks the CPython twin
and native JIT, AOT and abi3 extension, each native mode with normal GC and
collection at every allocation. It verifies scoring before/after alias mutation,
owner survival after all host batch references disappear, derived-view survival
after the parent handle closes, and owner finalization exactly once after
repeated explicit release. These correctness checks have no timing threshold.

## Protocol references

- [NumPy 2.1 `from_dlpack`](https://numpy.org/doc/2.1/reference/generated/numpy.from_dlpack.html): producer-object API and the explicit `copy=False` contract.
- [DLPack Python specification](https://dmlc.github.io/dlpack/latest/python_spec.html): CPU/device negotiation, single-consumer capsules and producer-deleter ownership.
