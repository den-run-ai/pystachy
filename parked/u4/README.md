# Parked: unions of a class template's specializations (U4), and the parsy probe

Stopped on 13 Oct 2026. Parsy support is no longer a goal (#193), and this work
is not planned. The branch keeps the unfinished compiler change and the
reproductions, so a future design can start from them. It is not for merge.

It is based on #238 (closed unions) at 65650b8, which is parked too.

## The unfinished change (`pystachy.py` in this branch's commit)

- **Field reads and method calls through a union** whose members are all classes:
  - field reads go through `Gen.uclasses()` and `ufield()`; method calls through `umethod()`;
  - each dispatches on the box's tag to the member's own object, so layouts and aliases are kept;
  - field types and returns are joined with `union_type()`: `T` with `None` gives `T | None`.
- **None-typed fields in a specialization:** `Result(False, None)` stores a null pointer.
- **`ukind()`** tells a template's specializations apart in a union by their own tags.

Not done:
- calling an object through a union (`__call__`);
- iterating a tuple whose items have different types;
- inferring an accumulator that starts as `None` and whose next value reads it;
- the review's boundary that field writes through a union stay rejected with a clear error.

## Reproductions

Each `NAME.out` holds CPython's output. The table gives each compiler's first error, or "matches CPython".

| program | what it needs | main + #239 | #238 (2cb891d) | this branch |
|---|---|---|---|---|
| `result_none.py` | a `None` field in one specialization (`Result(False, None)`) | cannot infer the type of field 'value' | same | matches CPython |
| `result_join.py` | `Result.success()`/`failure()` returning different specializations; field reads, `aggregate()`, `repr()`, lists of them | cannot infer the type of field 'value' | same | matches CPython |
| `parser_join.py` | a `Parser` holding `Callable[[str, int], Result]` whose functions return either specialization; `alt`, `then`, `parse` with errors | cannot infer the type of field 'value' | same | matches CPython |
| `union_call.py` | `pick(flag)` returning `Box(2)` or `Box("ab")`, then calling it | expected Box[int], got Box[str] | same | 'Box[int] \| Box[str]' object is not callable |
| `tuple_iter.py` | `for x in (1, "a")` | cannot iterate over tuple[int,str]: its items have different types | same | same |
| `selfref_accumulator.py` | `result = None`, then `result = R(...).agg(result)` in a loop (no union involved) | cannot infer the type of 'result' from None here, before a value of another type is assigned to it | same | same |

`selfref_accumulator.py` fails on main without any union: the local's type
can't be written down either, because an annotation that names a class template
types nothing.

## The parsy probe (`parsy_probe/`)

`port.py` applies 24 marked edits to parsy 2.2's `src/parsy/__init__.py`. The
sdist is `parsy-2.2.tar.gz`, SHA-256
`e943147644a8cf0d82d1bcb5c5867dd517495254cea3e3eb058b1e421cb7561f`, MIT. The
edits are in `port.py`, `e_regex.py` and `e_bytes.py`:

    python3 port.py UPSTREAM/src/parsy/__init__.py parsy.py e_regex.py e_bytes.py

The edits:
- streams are `str` only;
- `Any` is left out, so those parameters become template parameters;
- `Result` is a class template instead of a dataclass of `Any`;
- `max: int | float`;
- `regex()` no longer rebinds `exp` and `group`;
- `enum`, `functools.wraps` and `from_enum` are dropped.

`core.py` is the probe program: `regex("[0-9]+").map(int).parse("42")`.

With this branch's compiler, plus #239's two fixes, the probe stops in this order:
1. Every `parse()` runs `self << eof`, which becomes `seq(self, eof)`. That loops over a tuple of two different `Parser` specializations (`tuple_iter.py`).
2. It then calls `parser(stream, index)` through their union (`union_call.py`).
3. Then comes `result = parser(...).aggregate(result)` with `result = None` first (`selfref_accumulator.py`).

A prototype got past steps 1 and 2: about 10 lines to iterate such a tuple as a list of the items' union, and two hooks for `__call__`. Neither is in this branch.

Beyond those, the probe recorded four more needs:
- `then`/`skip`/`+` go through `combine(*res)`, a star call of a list;
- `@generate` needs generators with `.send()`;
- `forward_declaration` swaps `__dict__` and `__class__`;
- JSON values need recursive types.

The two class-template bugs this probe found are fixed in #239.
