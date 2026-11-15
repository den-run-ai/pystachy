# Port stored values with explicit typed interfaces

These examples let unrelated implementations share one field, list and consumer
using Pystachy's `Callable` support. They are source-level prototypes of the
stored-interface problem in [#488](https://github.com/den-run-ai/pystachy/issues/488).
The [integer iterator example](../../tests/programs/apps/example_typed_iterator.py)
and [generic interfaces example](../../tests/programs/apps/example_typed_interfaces.py)
run unchanged on CPython and are part of the normal differential corpus. The second
example also retains repeatable iterables and dictionaries or lists behind a
three-operation lookup interface.

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

The generic factory leaves the concrete source specialized while retaining its item
type for the nested callback:

```python
def typed_iterator(source: Iterable[T]) -> TypedIterator[T]:
    iterator = iter(source)

    def advance() -> T:
        return next(iterator)

    return TypedIterator(advance)
```

Pystachy specializes this small factory and closure for each concrete source. It
matches `Iterable[T]` to the supported source's item type when the wrapper needs
the nested callback's signature. The wrapper's fixed callable field checks that
item contract during compilation. Adaptation calls
`iter(source)` once, including any side effects of the source's `__iter__`. The adapter
does not itself call `next` or materialize the items; its closure retains that iterator.
On CPython, annotations do not enforce the item type at runtime; callers must meet
the documented contract.

This binding is separate from storage: `Iterable[T]` still leaves the factory's
argument concrete. The ordinary generic function's parameters and return retain
their existing inference rules; the fixed contract is established by the nested
callback and the wrapper's explicitly annotated fields. The original concrete
`int_iterator(source)` remains available when the boundary must require integers.

## 3. Keep the consumer shared

```python
from adapter import TypedIterator, typed_iterator

def drain(iterator: TypedIterator[int]) -> list[int]:
    return list(iterator)

streams: list[TypedIterator[int]] = [
    typed_iterator([1, 2]),
    typed_iterator((3, 4)),
]
print([drain(iterator) for iterator in streams])
```

The full example adds a custom iterator and a generator, then replaces a stored
field with another source kind. All integer sources use one compiled `drain` body.
The source-specific code stays in the adapters. Typed callables use indirect calls
and captured state; adapter construction adds allocations. This example establishes
a shared representation, not a speed or allocation improvement.

## 4. Retain an iterable without consuming it

A retained source and a retained iterator have different contracts. `TypedIterable[T]`
stores `Callable[[], TypedIterator[T]]`; its `__iter__` requests a new adapter.
`typed_iterable(source)` retains the source without calling `iter(source)` during
adaptation. Each later iteration calls it once. A list or tuple can therefore be
read repeatedly, while a generator remains a single-pass source:

```python
from adapter import TypedIterable, typed_iterable

def total(source: TypedIterable[int]) -> int:
    result = 0
    for value in source:
        result += value
    return result

sources: list[TypedIterable[int]] = [
    typed_iterable([1, 2]), typed_iterable((3, 4)),
]
print([total(source) for source in sources])
print([total(source) for source in sources])
```

The example checks delayed `__iter__` side effects, source mutation, field replacement
and generators' exhaustion. Neither adapter materializes the source. Both wrappers
have their own identities and retain their source through the existing closure
representation.

## 5. Choose several operations with fixed signatures

[`lookup.py`](lookup.py) applies the same pattern to `TypedLookup[K, V]`:

| Operation | Stored signature |
|---|---|
| `source[key]` | `Callable[[K], V]` |
| `key in source` | `Callable[[K], bool]` |
| `len(source)` | `Callable[[], int]` |

`dict_lookup(values)` captures a live dictionary; `index_lookup(values)` exposes
a live list under nonnegative integer keys. Each factory's nested callbacks retain
its inferred key and value bindings. For matching key/value types, the wrappers
share a layout and a consumer despite their different backing storage. Mutation
of the original dictionary or list remains visible. The index adapter deliberately
uses lookup semantics: out-of-range or negative keys raise `KeyError`.

This is an explicit three-operation contract. It provides neither mutation through
the wrapper nor the complete `Mapping` API. Choose the operations required by the
consumer, annotate their callable signatures, and keep any additional resource or
identity contract explicit. It uses existing closure and class machinery without
introducing a runtime method table or structural `Protocol` conversion.

## 6. Verify behavior and inspect the compiled interfaces

From the repository root, after [setup](../../docs/install.md), use the CPython
version in `.python-version`:

```sh
PYTHONPATH=examples/typed_iterator python3.13 tests/programs/apps/example_typed_iterator.py
make test-py FILES="tests/programs/apps/example_typed_iterator.py tests/errors/generators/typed_iterator_item_type.py"
make test FILES="tests/programs/apps/example_typed_iterator.py tests/errors/generators/typed_iterator_item_type.py"
PYSTACHY_GC_STRESS_PROGRAM=1 make test FILES="tests/programs/apps/example_typed_iterator.py"
make test-py FILES="tests/programs/apps/example_typed_interfaces.py"
make test FILES="tests/programs/apps/example_typed_interfaces.py"
PYSTACHY_GC_STRESS_PROGRAM=1 make test FILES="tests/programs/apps/example_typed_interfaces.py"
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

For the generic example, inspect `example_typed_interfaces.py` with `--function total`
or `--function read_keys`. The report records stored callable fields, concrete
adapters and indirect calls across the compilation graph even when the snapshot
selects one consumer. Function metadata records the retained type-variable bindings.
These are static observations; they do not count runtime calls or allocations.
The [interface benchmark](../../bench/typed_interfaces/README.md) measures dispatch,
construction, compilation and code growth separately.

## Limits when choosing this adaptation

The wrapper has its own identity and concrete type. It preserves shared underlying
iterator state, not identity with the source. It does not forward generator
`send`, `throw` or `close`, length hints, reflection or pickling. Keep a separate
resource-management contract where cleanup depends on those operations.

The factories require source operations and item types already supported by
Pystachy. A type variable needs a consistent supported binding before a local or
nested annotation can use it; unresolved or conflicting bindings do not create
dynamic storage. This is explicit adaptation, not automatic `Iterator[T]` or
structural `Protocol` support. Native erased interfaces
still need method compatibility, identity and GC rules and comparisons of dispatch,
allocation and code-size costs before replacing this prototype.
