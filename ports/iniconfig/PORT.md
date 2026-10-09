# iniconfig 2.3.1, ported to Pystachy

[iniconfig](https://pypi.org/project/iniconfig/) is the INI parser pytest uses to read
`pytest.ini`, `tox.ini` and `setup.cfg` (rank 25 on PyPI in October 2026). These are its three
modules from the sdist `iniconfig-2.3.1.tar.gz` (SHA-256
`67f4b9c50da0dedf52af349e7749a80a9057a5031199791b906c3bb3ae878960`), MIT licensed (`LICENSE`).

| file | upstream SHA-256 | edits |
|---|---|---|
| `exceptions.py` | `9a2a50fda3310fd0af4af156375a135d8e10b919ca00c6757f7b027668c34d4d` | none |
| `_parse.py` | `15824a78105b52aa9ed414ce6ad073967c73be7ea5ae9d991a0df97a6e0cc2e1` | 1 line |
| `__init__.py` | `bb1c9017eea0053a104bd0703f3d8d13e7b9a854e4a364ee765ad64da7220819` | 5 methods |

`_version.py` is left out: nothing imports it. Every edit is marked `# Pystachy port:` in the
source, and `diff -ru` against the sdist's `src/iniconfig` shows them all.

## The edits, and the feature each one stands in for

1. `_parse.py`: `"\N{BYTE ORDER MARK}"` is written `"\ufeff"`. Pystachy has no table of Unicode
   character names.
2. `SectionWrapper.get` and `IniConfig.get` lose `convert=` and take a `str` default. Their
   upstream signatures are generic over two `TypeVar`s and take a `Callable`, so their result is
   `str`, the default's type or `convert`'s: that needs functions as values (#8, M3) and unions of
   unrelated types (#9, M4). With a `str` default they behave as upstream.
3. `SectionWrapper.__iter__` sorts the names by their line number without a nested function,
   `key=` and `yield from` (#8, #12): it builds `(line, name)` pairs, sorts them, and returns an
   iterator over the names, which `list()` and `for` consume as they would the generator.
4. `IniConfig.__iter__` returns an iterator over a list instead of being a generator (#12),
   sorting as 3 does, and `SectionWrapper.items` returns the list of pairs itself: Pystachy takes
   `Iterator[T]` only as what `__iter__` returns.

Everything else compiles as it is: the `NamedTuple`, `str | None` and `list[str] | None` fields,
tuple keys with a `None` item (`dict[tuple[str, str | None], int]`), `int | None` results,
keyword-only parameters, `@classmethod` with `cls(...)`, `@overload` stubs, `Final`,
`collections.abc` annotations, `str | os.PathLike[str]`, `__getitem__`, `__contains__`,
`__iter__`, `try`/`except`/`else`, `raise ... from None`, and `ParseError`, a user exception
class with `super().__init__(...)` and `__str__`.

## Tests

`tests/port_iniconfig_parse.py` and `tests/port_iniconfig_api.py` run the cases of iniconfig's
own `testing/test_iniconfig.py` as programs, and `tests/run.sh` compares what they print with
CPython's, JIT and AOT. They leave out what the edits remove (`convert=int`, non-`str` defaults)
and `IniConfig(data=...)` without a path, which CPython rejects with a `TypeError` at run time and
Pystachy at compile time. Run under CPython against the unmodified upstream package, both print
exactly what they print against this port.
