# Core CPython case expansion

These standalone differential programs adapt selected CPython 3.13.16 test
methods at commit `cbc944f4bc59639a444dd971c737788ba2283a91`. They exercise
supported native APIs, including dynamic `Any` storage. They are not a run of the full
CPython test suite, and passing them does not imply support for an entire module.
The upstream PSF license is [CPYTHON-LICENSE.txt](CPYTHON-LICENSE.txt).

| Program | Upstream source and methods | Scope and adaptations |
|---|---|---|
| [upstream_json_decode_core.py](../programs/upstream/upstream_json_decode_core.py) | `Lib/test/test_json/test_decode.py`: `test_nonascii_digits_rejected`, `test_constant_invalid_case`, `test_empty_objects`, `test_decoder_optimizations`, `test_keys_reuse`, `test_extra_data`, `test_invalid_escape`, `test_string_with_utf8_bom` | Preserve data and assertions for `loads(str)`, including repeated-key identity. Replace unittest with assertions. Use a literal BOM instead of a codec construction; exclude the file-API and decoder-internal `memo` checks. Also compare error source and character coordinates. |
| [upstream_json_encode_dynamic.py](../programs/upstream/upstream_json_encode_dynamic.py) | `Lib/test/test_json/test_dump.py`: `test_encode_truefalse`, `test_encode_mutated` | Preserve mixed bool/int/float-key outputs and a callback shrinking its input list. An ordinary user object replaces `object()` and the callback moves to module scope. Add callback-count and surviving-length assertions. |
| [upstream_json_recursion_dynamic.py](../programs/upstream/upstream_json_recursion_dynamic.py) | `Lib/test/test_json/test_recursion.py`: `test_listrecursion`, `test_dictrecursion` | Preserve direct/indirect cycles and repeated aliases with explicit `Any` annotations. Also encode the repeated-dict-alias parent; upstream only encodes the child in that final check. |
| [upstream_dict_dynamic_values.py](../programs/upstream/upstream_dict_dynamic_values.py) | `Lib/test/test_dict.py`: fragments of `test_setdefault`, `test_pop`, `test_repr`, and `test_hash_collision_remove_add` | Restore heterogeneous defaults/values, recursive repr, and the original identity-based `CustomHash` keys with 64 distinct hashes plus a collision. Use explicit storage annotations, omit unused nondeterministic repr, and pass the default `None` explicitly to `setdefault`; its omitted-default form remains unsupported ([#774](https://github.com/den-run-ai/pystachy/issues/774)). Error-arity and callback-exception parts are not included. |
| [upstream_deque_dynamic.py](../programs/upstream/upstream_deque_dynamic.py) | `Lib/test/test_deque.py`: comparison fragments of `test_count`, full-deque insertion from `test_insert_bug_26194`, `test_copy_method` | Explicit `deque[Any]` and `list[Any]` preserve heterogeneous values. User comparisons must run and propagate exceptions; mutation must be detected. Spell `list('ABC')` as `['A', 'B', 'C']` because a typed `list[str]` does not implicitly become `list[Any]`. Add shallow-alias assertions. |
| [upstream_difflib_context.py](../programs/upstream/upstream_difflib_context.py) | `Lib/test/test_difflib.py`: context-diff halves of `TestOutputFormat.test_tab_delimiter` and `test_no_trailing_tab_on_empty_filedate`, plus full `test_range_format_context` | Preserve context-diff expected strings; replace unittest scaffolding with assertions. Add 11 bounded public-API boundary scenarios. Unified-diff halves already have coverage elsewhere. |

All inputs stay small: no interpreter recursion-limit manipulation, large-memory
fixtures, networking, subprocess services or optional extension dependencies.
Full `unittest`/`test.support`, CPython C-API/refcount/GC internals, runtime class
mutation, builtin subclasses and unsupported codec APIs remain outside these
adaptations. JSON decoding hooks, bytes/file inputs, encoder subclasses, indentation,
arbitrary-precision integers and 100,000-level nesting are not validated here.
`copy.deepcopy` is not implemented by the copy-method tests.

The historical exclusions in older `upstream_*.py` headers describe those files'
adaptations. This expansion supplements them; it does not silently broaden the
scope of their original upstream-method counts.

## Source identities

These are SHA-256 hashes of the complete unmodified files fetched from the pinned
commit, independently checked against GitHub's Git blob IDs before selecting
methods. The adaptations above do not execute the upstream unittest scaffolding.

| Source under `Lib/test/` | SHA-256 |
|---|---|
| `test_json/test_decode.py` | `4e6a52a0dd3bb1e44cfd8cfd09ac273930d178639e03e0e649483d3b1e41f8cf` |
| `test_json/test_dump.py` | `e5eaeec50d6127c4c5c2fe1dfecc17f72e82034612c84d9d72bfbde1c241f758` |
| `test_json/test_recursion.py` | `2c57611f84f30f50b96aff177e656e163316aba838994d2f36b82698752442a2` |
| `test_dict.py` | `ab8c3107f3390867750c19a3024c0284c34c62fb6f2297024627b1c66b48d406` |
| `test_deque.py` | `15578b602865dfa5c80baa64006d64c5875765aab457d5b4bedd73a5e8436d73` |
| `test_difflib.py` | `dc6b140c8dd31e6971888070ea5175a0ab72ecadbdc96956071ceb062f34e636` |

## Reproduction

Use the repository's pinned Python to record expectations, then the normal
native differential harness. The `upstream_json_*` selector currently names
these three JSON cases; the other selectors name the dictionary, deque and context-diff cases.

```sh
PYTHON=python3.13 tests/record.sh upstream_json_decode_core upstream_json_encode_dynamic upstream_json_recursion_dynamic upstream_dict_dynamic_values upstream_deque_dynamic upstream_difflib_context
PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/upstream/upstream_json_*.py tests/programs/upstream/upstream_dict_dynamic_values.py tests/programs/upstream/upstream_deque_dynamic.py tests/programs/upstream/upstream_difflib_context.py
PYSTACHY_GC_STRESS_PROGRAM=1 PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/upstream/upstream_json_*.py tests/programs/upstream/upstream_dict_dynamic_values.py tests/programs/upstream/upstream_deque_dynamic.py tests/programs/upstream/upstream_difflib_context.py
```

The normal corpus discovery includes these programs in hosted/native, JIT/AOT,
GC-stressed, unoptimized and sanitizer verification configurations. Recorded
stdout is derived only from CPython, including the final exit status.
