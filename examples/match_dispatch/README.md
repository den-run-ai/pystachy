# Typed command dispatch with `match`

[`dispatch.py`](dispatch.py) parses a small command language and applies commands
to an integer accumulator. The same source runs under CPython, native JIT and AOT:

```sh
python3 examples/match_dispatch/dispatch.py
./pystachy run examples/match_dispatch/dispatch.py
./pystachy build examples/match_dispatch/dispatch.py -o build/match-dispatch
build/match-dispatch
```

The successful sequence prints `[7, 5, 15, 0, -4]`, followed by four expected
validation errors. `parse()` uses a fixed tuple, literal alternatives and a guard;
`apply()` uses positional and keyword patterns over a concrete dataclass. Invalid
commands follow ordinary `ValueError` handling. `evaluate()` returns every
intermediate result, making changes in order observable.

The eleven cases in `test_dispatch.py` share an original pytest oracle with the
native test runner and are registered in the ordinary example CI group:

```sh
python3 -m pytest -q examples/match_dispatch
python3 tools/pytest_native_suites.py --suite match_dispatch --compiler ./pystachy
```

The result of `split()` is a variable-length list. The explicit length check and
fixed tuple make the example fit the bounded sequence-pattern contract. Class
matching uses initialized plain fields on a statically known dataclass. Mapping
patterns, general list matching and custom `__match_args__` are outside this
example's scope.

The separate [dispatch benchmark](../../bench/match_dispatch/README.md) compares
equivalent `match` and handwritten branches without changing this example.
