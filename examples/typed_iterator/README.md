# Port a stored iterator with an explicit typed interface

This example lets unrelated integer iterators share one field, list and consumer
using Pystachy's existing `Callable` support. It is a source-level prototype of the
stored-interface problem in [#488](https://github.com/den-run-ai/pystachy/issues/488).
The executable example is
[`example_typed_iterator.py`](../../tests/programs/apps/example_typed_iterator.py);
it runs unchanged on CPython and is part of the normal differential corpus.

## 1. Identify the storage boundary

Try the original component first. An unannotated function can specialize for each
concrete argument type; it does not automatically need dynamic `Any`. A different
problem arises when one field or collection must retain unrelated implementations.
An `Iterable[int]` annotation currently does not give that storage a common native
representation; see [typing](../../docs/language/typing.md).

Choose the operations the consumer actually needs. Here they are `iter` returning
the same iterator and `next` returning an `int` or propagating an exception. The
consumer needs a single-pass iterator, not a source it can restart.

## 2. Give stored callbacks a fixed signature

[`adapter.py`](adapter.py) defines a generic wrapper with one explicitly typed field:

```python
class TypedIterator(Generic[T]):
    def __init__(self, advance: Callable[[], T]) -> None:
        self._advance: Callable[[], T] = advance

    def __iter__(self):
        return self

    def __next__(self) -> T:
        return self._advance()
```

The field annotation matters: it stores the callable's signature instead of the
concrete function or closure type. Different captured iterator types can therefore
share `TypedIterator[int]`. The example also checks `TypedIterator[str]` with a
separately annotated string callback.

The integer factory leaves its source parameter unannotated on purpose:

```python
def int_iterator(source) -> TypedIterator[int]:
    iterator = iter(source)

    def advance() -> int:
        return next(iterator)

    return TypedIterator(advance)
```

Pystachy specializes this small factory and closure for each concrete source. The
`int` return annotation checks the item contract during compilation. Adaptation calls
`iter(source)` once, including any side effects of the source's `__iter__`. The adapter
does not itself call `next` or materialize the items; its closure retains that iterator.
On CPython, annotations do not enforce the item type at runtime; callers must meet
the documented contract.

## 3. Keep the consumer shared

```python
from adapter import TypedIterator, int_iterator

def drain(iterator: TypedIterator[int]) -> list[int]:
    return list(iterator)

streams: list[TypedIterator[int]] = [
    int_iterator([1, 2]),
    int_iterator((3, 4)),
]
print([drain(iterator) for iterator in streams])
```

The full example adds a custom iterator and a generator, then replaces a stored
field with another source kind. All integer sources use one compiled `drain` body.
The source-specific code stays in the adapters. Typed callables use indirect calls
and captured state; adapter construction adds allocations. This example establishes
a shared representation, not a speed or allocation improvement.

## 4. Verify behavior and inspect the compiled interface

From the repository root, after [setup](../../docs/install.md), use the CPython
version in `.python-version`:

```sh
PYTHONPATH=examples/typed_iterator python3.13 tests/programs/apps/example_typed_iterator.py
make test-py FILES="tests/programs/apps/example_typed_iterator.py tests/errors/generators/typed_iterator_item_type.py"
make test FILES="tests/programs/apps/example_typed_iterator.py tests/errors/generators/typed_iterator_item_type.py"
PYSTACHY_GC_STRESS_PROGRAM=1 make test FILES="tests/programs/apps/example_typed_iterator.py"
```

`test-py` hosts the compiler on CPython; both `test-py` and `test` execute the
program natively in JIT and AOT modes. The recording checks values, ordering,
one source `iter` call, no prefetch, shared partial consumption, live list mutation,
repeated exhaustion, source exceptions and retained closure state. A separate
rejection case prevents string items from entering the integer contract.

Use a new output directory for [compiler inspection](../../docs/compiler-inspection.md):

```sh
PYSTACHY_PATH=examples/typed_iterator python3.13 tools/inspect_compiler.py \
  tests/programs/apps/example_typed_iterator.py \
  --output /tmp/pystachy-typed-iterator --typed-after-only --function drain
```

Read `report.json` for a successful compilation, then `typed-after.json` for the
single `drain` signature, its wrapper parameter and `list[int]` result. The final
attempt's `class_specializations` records the wrapper's callable field. The hosted
inspection test checks the shared integer representation and absence of dynamic
`Any` dispatch. Inspection observes emitted specializations; it does not execute
the program or certify every possible use of the module.

## Limits when choosing this adaptation

The wrapper has its own identity and concrete type. It preserves shared underlying
iterator state, not identity with the source. It does not forward generator
`send`, `throw` or `close`, length hints, reflection or pickling. Keep a separate
resource-management contract where cleanup depends on those operations.

The factory requires an integer iterable already supported by Pystachy. A fully
generic `Iterable[T]` factory with a nested `-> T` callback remains outside this
example; use a concrete callback signature. This is explicit adaptation, not
automatic `Iterator[T]` or structural `Protocol` support. Native erased interfaces
still need method compatibility, identity and GC rules and comparisons of dispatch,
allocation and code-size costs before replacing this prototype.
