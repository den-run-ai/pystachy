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
| [upstream_shlex_punctuation.py](../programs/upstream/upstream_shlex_punctuation.py) | `Lib/test/test_shlex.py`: `testSyntaxSplitAmpersandAndPipe`, `testSyntaxSplitSemicolon`, `testSyntaxSplitRedirect`, `testSyntaxSplitParen`, `testSyntaxSplitCustom`, `testTokenTypes`, `testPunctuationInWordChars`, `testPunctuationWithWhitespaceSplit`, `testPunctuationWithPosix`, `testEmptyStringHandling`, `testUnicodeHandling`, `testQuote`, `testJoin`, `testLinenoAfterNewLine`, `testLinenoAfterComment`, `testPushToken`, `testPushTokenLifo`, `testPushSourceString`, `testPushSourceStream`, `testErrorLeaderTracksPosition`, `testErrorLeaderOverrides`, `testNoClosingQuotation`, `testNoEscapedCharacter` | Every input and assertion is kept; `subTest` becomes a loop. `testTokenTypes` adds `t is None` to its EOF test because comparing with `s.eof` does not narrow `get_token()`'s `str \| None`; non-POSIX shlex returns `''` at EOF, so behaviour is unchanged. `unittest.mock` debug-output, file/sourcehook and read-only-property methods are excluded. |
| [upstream_posixpath_strings.py](../programs/upstream/upstream_posixpath_strings.py) | `Lib/test/test_posixpath.py`: str halves of `test_join`, `test_split`, `test_splitext` (`splitextTest`), `test_splitroot`, `test_isabs`, `test_basename`, `test_dirname`, and `test_normpath` with all 50 `NORMPATH_CASES` | Every str input and assertion is kept. Bytes halves are excluded because `lib/posixpath` supports str paths; file-system, `realpath`, `expanduser`, `relpath` and `commonpath` methods are excluded. |

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
| `test_shlex.py` | `943ddf74ffa1da625169221d17e84f386314016da36bc3696ebcdb9ca88b039d` |
| `test_posixpath.py` | `34ada45f0e4f0e2b8326404b7e7dbf1416a079081f6e0a1f90ab9d691e9a8be8` |

## Reproduction

Use the repository's pinned Python to record expectations, then the normal
native differential harness. The `upstream_json_*` selector currently names
these three JSON cases; the other selectors name the dictionary, deque, context-diff, shlex and posixpath cases.

```sh
PYTHON=python3.13 tests/record.sh upstream_json_decode_core upstream_json_encode_dynamic upstream_json_recursion_dynamic upstream_dict_dynamic_values upstream_deque_dynamic upstream_difflib_context upstream_shlex_punctuation upstream_posixpath_strings
PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/upstream/upstream_json_*.py tests/programs/upstream/upstream_dict_dynamic_values.py tests/programs/upstream/upstream_deque_dynamic.py tests/programs/upstream/upstream_difflib_context.py tests/programs/upstream/upstream_shlex_punctuation.py tests/programs/upstream/upstream_posixpath_strings.py
PYSTACHY_GC_STRESS_PROGRAM=1 PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/upstream/upstream_json_*.py tests/programs/upstream/upstream_dict_dynamic_values.py tests/programs/upstream/upstream_deque_dynamic.py tests/programs/upstream/upstream_difflib_context.py tests/programs/upstream/upstream_shlex_punctuation.py tests/programs/upstream/upstream_posixpath_strings.py
```

The normal corpus discovery includes these programs in hosted/native, JIT/AOT,
GC-stressed, unoptimized and sanitizer verification configurations. Recorded
stdout is derived only from CPython, including the final exit status.

## Mechanical method extraction (2026-11-02)

[`tools/cpython_test_methods.py`](../../tools/cpython_test_methods.py) turns the unittest
methods of a CPython test file into standalone programs by fixed rules, with no per-test
editing: unittest/test.support imports and their users are dropped; a pure-Python
`import_fresh_module` result becomes a plain import (C-accelerator variants and their test
classes are dropped) and `self.module` is inlined; `setUp()` becomes `__init__()`; assertion
methods become `assert` statements of the same condition, `assertRaises`/`assertRaisesRegex`
become try/except/else (the regex is still checked), `subTest` keeps its body; skip,
`cpython_only` and `requires_*` tests are left out. Each program keeps only the definitions and
the one test it needs; a program whose tests use `random` seeds it with 0 before each test, so
every run draws the same inputs. A method that needs another unittest feature raises
`NotImplementedError`, so it cannot pass by accident. The tool's docstring has the complete
rules, and `tools/test_cpython_test_methods.py` (run by Lint) checks them, including negative
controls for false assertions and exceptions that are not raised.

### Triage

On main `8563b854`, 144 CPython 3.13.16 test files for builtins, the language and the
modules Pystachy ships or that the core scope names were triaged with
`tools/cpython_test_methods.py triage` (CPython 3.13.16, the native compiler's JIT); 140 of
them hold extractable methods:

| Result | Methods |
|---|---:|
| Extracted | 10,329 |
| Fail on CPython after extraction (unittest/test.support features beyond the rules): not counted | 4,314 |
| Compile and match CPython | 374 |
| Match once the program opts in to promoting ints | 7 |
| Rejected at compile time | 5,617 |
| Compile but differ | 17 |

That is **381 of 6,015 (6.3%)** methods passing with no hand edit. All 17 differences are
documented deviations, not new wrong results: 13 raise `OverflowError` past 64 bits in
modules without promoting ints (`lib/random`'s too), one asks for the unsupported `utf-16`
codec, two use bytes patterns and one compares `repr(re.I)`, as `re`'s flags are ints
([lib/compatibility.md](../../lib/compatibility.md)). Seeding `random` makes one test fail
under CPython itself: `TestPStdev.test_compare_to_variance` compares two float results on
random data exactly, and they differ for seed 0, so it counts as not runnable.

Missing modules account for 2,884 of the rejections, led by `enum` (1,016 methods, nearly
all of `test_enum`), `configparser`, `decimal`, `pickle` (25 files), `copy` (16 files), `gc`,
`_pyio`, `locale`, `pprint`, `threading`, `calendar`, `inspect` and `array`. The most frequent
other rejections are a class defined inside a function (296 methods in 49 files), fields
whose type is not inferred, often because a test class stores a class it calls
(`self.s = self.thetype(...)`), `match` (`test_patma`), base classes other than an ordinary
class (builtin subclasses, 176), modules used as values (62), inheritance from generic class
templates (63), statements other than definitions in a class body (126), empty containers
whose type is not inferred (83), `str.format()` of a computed format string (49) and
multiple inheritance (40).

### Delivered programs

The corpus takes the passing methods of the 20 files that no earlier adaptation covers, one
program per file (`tests/programs/upstream/upstream_NAME_extracted.py`), and a separate
promoting-int program where a file's passing tests need it. Files whose passing methods
overlap an existing hand adaptation (`test_named_expressions` 37, `test_fstring` 28,
`test_urlparse` 21, `test_textwrap` 19, `test_random` 18, `test_difflib` 16, `test_math` 16,
`test_float` 13, `test_fnmatch` 13, `test_scope` 12, `test_statistics` 11 and others) are not
added again; their passing methods are candidates for extending those adaptations.

| Program | Tests | Source under `Lib/test/` and SHA-256 |
|---|---:|---|
| `upstream_augassign_extracted` | 2 | `test_augassign.py` `fa336b354cb98b5e290f71d9565cc0c1fc26d603450c9b96a2ee2a927ff99ea6` |
| `upstream_bisect_extracted` | 3 | `test_bisect.py` `c2cc55581e637768faa0f51cbb66acbaa6664eb023e287b37db687faefa2c1c4` |
| `upstream_bytes_extracted`, `upstream_bytes_extracted_python_int` | 17 + 1 | `test_bytes.py` `aae9cf5348faa9b39bdccb13489e14facb6cdf51bfa5310a75518608645f6e06` |
| `upstream_colorsys_extracted` | 7 | `test_colorsys.py` `f48dd64aaf7497c5f5809803345581f1daac03d5a5ed148a661066d0200d7661` |
| `upstream_dictviews_extracted` | 1 | `test_dictviews.py` `f6e290a9cda996fd2531e20902cb99fd8785da069a31e27038daed194b3295e2` |
| `upstream_exception_variations_extracted` | 16 | `test_exception_variations.py` `1d7b1fa4bdae0354b9981db98001b2ad7ab83894c1701a83db2a434d0036cebf` |
| `upstream_heapq_extracted` | 2 | `test_heapq.py` `ab72726259119159f060aa80274efb33e53a5455636bd5aa16f923535375b348` |
| `upstream_int_literal_extracted`, `upstream_int_literal_extracted_python_int` | 3 + 3 | `test_int_literal.py` `2dd1dd8ca1e049abef5e5548179aba2532952f9f5362bc7c6d09bd73f80c5974` |
| `upstream_opcodes_extracted` | 1 | `test_opcodes.py` `2c30b2eeffad6d2b8eefa0bea40b7a7ce1e3674c5b6912805d81f1b3455d9c11` |
| `upstream_positional_only_arg_extracted` | 1 | `test_positional_only_arg.py` `3f34be8648b28a6baccb20d65ee65241a14ae2494cf9e3cfc4d12b7362358f6b` |
| `upstream_pow_extracted` | 2 | `test_pow.py` `0cfbf5bc3b271db92d5f728c649b9501b4c786d42db74bc75afeb41a54dde27d` |
| `upstream_raise_extracted` | 12 | `test_raise.py` `ff1037ebdfb6b1f8900041bbb4b39d26441ed25b13783368169cda6e57bc8647` |
| `upstream_range_extracted` | 3 | `test_range.py` `603d1ca7b740d2e4702b3ff42202de4c261b41d51078227526c7447caa3bf80e` |
| `upstream_reprlib_extracted` | 1 | `test_reprlib.py` `ec84a6d632f43fce37efde8f18f6507dfec899bbbdae99000326a8c30fe17621` |
| `upstream_richcmp_extracted` | 1 | `test_richcmp.py` `87ffd49f08a617224cdbb84f0eeb7cef643f3cd918090c606a311a25d929d135` |
| `upstream_sort_extracted` | 8 | `test_sort.py` `dd8cee99c70a21f6a220f64bf40e2ab9099c6df79f15859577cea4c4377fb382` |
| `upstream_types_extracted` | 8 | `test_types.py` `9ecf8e399e30e83794a1fafc34c5b990da2fa469c980e2f2157eeedc1b118d24` |
| `upstream_unary_extracted` | 2 | `test_unary.py` `867adb0ac3eddbe957c0137a84f2dbac75bfd09c0a8b51e3e75a7af9eaa3f8eb` |
| `upstream_unicodedata_extracted` | 1 | `test_unicodedata.py` `0c2dda3daca931131fecc7241215f5eb484a705ad7bcc2aab110c2d838cf95ad` |
| `upstream_with_extracted` | 1 | `test_with.py` `dbcf093c3ed4e5be77fd6f345c178d545b7cd741f73dcac2a55cf97596e84b7f` |

Each program's header names its tests. Together they hold 96 tests; under the opted-in
`dynamic-any` sweep, `upstream_colorsys_extracted` is an expected failure (`f(*value)` of an
`Any` value, #774). Under the promoting-int sweep, two are (#907):
`upstream_augassign_extracted`, whose `x /= 2` rebinds a promoting int to a float, and
`upstream_bytes_extracted`, whose `bytes(sys.maxsize + 1)` is rejected because `bytes()`
takes no promoting int. Each source's SHA-256 is that of the file at the pinned commit (fetched
from GitHub) and of the python.org `Python-3.13.16.tar.xz` source archive, which also matches
every hash in this guide's earlier table.

Regenerate a program from a `Lib/test` checkout of the pinned commit, then record it with
the pinned CPython:

```sh
python3.13 tools/cpython_test_methods.py triage triage.json build/methods Lib/test/test_sort.py
python3.13 tools/cpython_test_methods.py combine Lib/test/test_sort.py tests/programs/upstream/upstream_sort_extracted.py TestBase.test_small_stability ...
PYTHON=python3.13 tests/record.sh upstream_sort_extracted
PYSTACHY_JOBS=2 tests/run.sh ./pystachy 'jit aot' tests/programs/upstream/upstream_*_extracted*.py
```

`combine` writes the program without the provenance header the delivered files carry.

## Post-stdlib sample for v0.2.0

All methods from three complete CPython 3.13.16 files were extracted at
`cbc944f4bc59639a444dd971c737788ba2283a91`. The table compares the parent of
the stdlib merge (`8444af96`) with `6d9b1a3c`. Both use the same extractor,
CPython, checked-integer policy and LLVM 18.1.3 on Linux x86-64. A CPython
qualification requires the success marker and zero exit status. A JIT match
also requires identical stdout and stderr. Class/method skip decorators exclude
cases up front, and reaching `skipTest()` excludes a case during qualification.

| Source | Skipped by decorator | Extracted | CPython qualified | JIT matches before → after |
|---|---:|---:|---:|---:|
| `test_copy.py` | 0 | 81 | 76 | 0 → 12 |
| `test_glob.py` | 5 | 20 | 0 | — |
| `test_filecmp.py` | 0 | 16 | 6 | 0 → 0 |

The 12 gains executed shallow/deep-copy and exception assertions. The old
compiler rejected all 12 on the missing `copy` import. Remaining eligible copy
methods encounter nested classes, untyped empty containers and unsupported
APIs. The `glob` methods need the discarded `test.support` filesystem fixture.
The six eligible `filecmp` methods still encounter a missing module.

The new corpus programs are `upstream_copy_extracted` (all 12 default-policy
matches) and `upstream_copy_extracted_any` (two additional methods with
heterogeneous lists/dicts under explicit dynamic Any). Both pass JIT and AOT,
normally and with `PYSTACHY_GC_STRESS_PROGRAM=1`. The dynamic tests assert
identity as well as equality of nested copies. The matched method IDs and order
are in their CPython-recorded `.out` files.

To repeat on each compiler checkout, run this extractor with its absolute
`--compiler` command, set `PYSTACHY_HOME` to that checkout, and use separate
work/output directories. Use one worker and a private `TMPDIR` because some
`filecmp` tests use fixed names under the temporary directory.

```sh
python3.13 tools/cpython_test_methods.py triage --compiler "$compiler" -j 1 \
  "$out/triage.json" "$out/methods" "$cpy/Lib/test/test_copy.py" \
  "$cpy/Lib/test/test_glob.py" "$cpy/Lib/test/test_filecmp.py"
```

The wider census also found all five methods of `LockContextTestCase` in
`Lib/test/test_contextlib.py`. [The combined fixture](../programs/upstream/upstream_contextlib_locks.py)
exercises single-thread lock, RLock, condition and semaphore state across
normal exit and exception unwinding. It retains the upstream inputs and
assertions and records the bounded and unbounded semaphore variants separately.
The pre-stdlib compiler rejects the `threading` import.
