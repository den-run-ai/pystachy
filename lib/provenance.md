# Library provenance and validation

Upstream-derived modules use CPython 3.13.16. Unchanged copies and their SHA-256
hashes remain in [README.md](README.md#unchanged-cpython-files), where
`tests/record.sh --check` verifies them. The hashes below identify original
upstream files, rather than the adapted file's current contents.

## Adapted Python modules

Each localized adaptation is marked `# Pystachy port:` in source. Common changes
add container/optional annotations, replace iterator-only paths with supported
consumers, and make C-only or dynamic imports optional. Detailed edit history
belongs in the source diff; [compatibility.md](compatibility.md) records the
observable contract.

| Module | Upstream file | Original SHA-256 |
|---|---|---|
| `html` | `Lib/html/__init__.py` | `923d82d821e75e8d235392c10c145ab8587927b3faf9c952bbd48081eebd8522` |
| `html.entities` | `Lib/html/entities.py` | `d9c65fb2828dbc1f3e399058a341d51e9375ec5bca95a8e92599c41bd5b78bde` |
| `html.parser` | `Lib/html/parser.py` | `4274e9112adf3fa57c7f9afa7c9b5c631456b18b7403cc627cc5027d02cdd2ae` |
| `_markupbase` | `Lib/_markupbase.py` | `cb14dd6f2e2439eb70b806cd49d19911363d424c2b6b9f4b73c9c08022d47030` |
| `difflib` | `Lib/difflib.py` | `1593ae08143632f4f81fea3beeeb279d803f8a9be922b12fe79664d78bba879d` |
| `getopt` | `Lib/getopt.py` | `0ce875700c8798193b8e2748f7a27fc542cc4d525a1e6fc403767450ec92be99` |
| `heapq` | `Lib/heapq.py` | `6d43277e5c76fc0f073cd388fcff852d14d068f6bb6d4886c340f8b75a1229a9` |
| `fnmatch` | `Lib/fnmatch.py` | `95391dac2ce9f60084d65eba2f4b9d9735e28136d55b684e1fde7d6342555963` |
| `textwrap` | `Lib/textwrap.py` | `30f3d833950d53e168cc021961574b553f56aed84458712b2eb29c6495843d46` |
| `string` | `Lib/string.py` | `c000d9c4340c910b869399f0f0acc1b70e39391ad9344c4e08d8d0f80210a916` |
| `operator` | `Lib/operator.py` | `c048f8a6852832d5fa750d6ae772d7658c52c3511d261cb902f7edfd262e9127` |
| `statistics` | `Lib/statistics.py` | `80b677e786418c299ced99993f4a89804d4532e0b5e26971286713a6de538c18` |
| `urllib.parse` | `Lib/urllib/parse.py` | `491b233e8d87a2ab73964afff029717177d53ad8def328ed9b00575db983da27` |
| `contextlib` | `Lib/contextlib.py` | `c1e0d67b2007de11ae93cd36cf6faf38d9ab32656a832d592a49325eec579f96` |
| `html` | `Lib/html/__init__.py` | `923d82d821e75e8d235392c10c145ab8587927b3faf9c952bbd48081eebd8522` |
| `html.entities` | `Lib/html/entities.py` | `d9c65fb2828dbc1f3e399058a341d51e9375ec5bca95a8e92599c41bd5b78bde` |
| `keyword` | `Lib/keyword.py` | `18c2be738c04ad20ad375f6a71db34b3823c7f40b0340f5294d0e89f3c9b093b` |
| `token` | `Lib/token.py` | `1d2ab814992e6afbd6f1e5323edcddd681f65f7679ad1eb87fe1357a433a5bdf` |
| `shlex` | `Lib/shlex.py` | `f927227de5ba5b1b2bdd75e3d9c8cb72b602b3bba3cc8edbf8fb554de0dc1fd7` |
| `random` | `Lib/random.py` | `fb2625eb54412c880e8f1af449785a74e125556159fc7997814e51dd054cc5da` |
| `datetime` | `Lib/_pydatetime.py` | `9a6652ecbdc8bcb9774136febc36b13f99aa926c7b42c19ac77e6c84128560a4` |
| `codecs` | `Lib/codecs.py` | `2f278497548b8313580b247a1097a0a304e5087a355ebb11a92ec685fa9e63ff` |

`heapq` adapts its top-k routines while retaining the other upstream code.
`datetime` is `_pydatetime`, which CPython's `Lib/datetime.py` re-exports when its C
accelerator is missing. Where CPython's accelerator behaves differently, the edits follow
`Modules/_datetimemodule.c` (SHA-256
`56cb991f5244e79edb81de4a0b45ae4138fe4270bd82920e4ed9eb957dc08e5a`): messages, float
`timedelta` arguments, ISO 8601 parsing, comparisons and the `strftime()` format scan.
Its `strftime()` reproduces `Modules/timemodule.c` (SHA-256
`695d4f627d2ff472c0bf4df4583bf97ea832b96b0cc9a7eb1f13ddd51ee19deb`) on glibc: ASCII runs
formatted as glibc 2.39's C-locale `wcsftime()` formats them, within its growing buffer.
`operator` adapts only its getter classes, whose closures become `__call__` code
reading constants. `string` adapts `Formatter` and takes `_string`'s parsers
from `_pystachy_string`.
`statistics` also ports `math_sumprod_impl` from `Modules/mathmodule.c` for
weighted means, and `random` ports its `m_lgamma`, `lanczos_sum` and `m_sinpi`
for `binomialvariate`. `urllib.parse` includes codec logic corresponding to CPython's
`unicodeobject.c`, `stringlib/codecs.h` and `codecs.c`, plus bracketed-host and
NFKC-delimiter validation. These modules keep CPython-only paths available when
CPython runs the source.

## Subset implementations

| Module | Upstream reference | Implementation |
|---|---|---|
| `io` | `Modules/_io/stringio.c`, `Modules/_io/bytesio.c`, `Modules/_io/textio.c` | Typed `StringIO` and `BytesIO`, with append chunks joined when read; `TextIOWrapper`, generic over its buffer's class, with the C type's chunks, decoders and messages |
| `types` (`_pystachy_types`) | `Lib/types.py` (SHA-256 `3a289bc5366e96d01017038870b5b8861b87305d351b99c688bcc681d908fa7d`) | The module's docstring and its names: `TracebackType`, as `from types import TracebackType` imports it for `__exit__`'s annotation, and the others, of which the compiler supports `GenericAlias` in `__class_getitem__ = classmethod(GenericAlias)` |
| `csv` | `Modules/_csv.c`, `Lib/csv.py` | Reader state machine, writer and dialect APIs |
| `collections.deque` | `Modules/_collectionsmodule.c` | Typed two-list queue with CPython comparison-state checks |
| `collections.defaultdict` | `Modules/_collectionsmodule.c` | Typed dict wrapper with the C type's factory, repr and `\|` |
| `collections.OrderedDict` | `Lib/collections/__init__.py`, `Objects/odictobject.c` | Two typed dicts, the first items reversed, with the Python class's docstrings and the C type's messages |
| `collections.Counter` | `Lib/collections/__init__.py` | Typed dict wrapper keeping the Python class's methods and docstrings |
| `collections.namedtuple` | `Lib/collections/__init__.py` | Made by the compiler (`Loader.nt_class`): the function's argument checks and messages, and a NamedTuple class template for the class |
| `functools` | `Modules/_functoolsmodule.c`, `Lib/functools.py` | Generic cache wrapper, plus adapted reduction, comparison-key and `partial` fallbacks, and the unchanged `update_wrapper()` and `wraps()`, which the compiler applies |
| `_pystachy_string` | `Objects/stringlib/unicode_format.h`, `Objects/unicodeobject.c` | `_string.formatter_parser()` and `formatter_field_name_split()`, returning lists |
| `re` | `Lib/re/`, `Modules/_sre/sre_lib.h`, `sre.c` | Typed parser/compiler and matching engine with an explicit context stack |
| `_pyrandom` | `Modules/_randommodule.c`, `Python/pyhash.c` | `_random.Random`'s Mersenne Twister, seeding and state; float hashing for float seeds |
| `binascii` (`_pystachy_binascii`) | `Modules/binascii.c`, `Python/pystrhex.c` | All twelve functions of the C module, with its errors and messages |
| `atexit` (`_pystachy_atexit`) | `Modules/atexitmodule.c` (SHA-256 `a61f11e295d38463b36524e51b8eba64d5a84022bb7df7b3c0ccd8aa9fe9521b`) | `register()`, `_clear()`, `_run_exitfuncs()` and `_ncallbacks()`, with the C module's order of callbacks; `unregister()` raises `NotImplementedError` |
| `abc` (`_pystachy_abc`) | `Lib/abc.py` (SHA-256 `e558702a95cdce3febd289da021715d2b92bc43995b8a1bc58dfa1c3d8010287`), `Modules/_abc.c`, `Objects/typeobject.c` | `ABC`, `ABCMeta`, `abstractmethod()` and the deprecated decorators, which the compiler applies, with `object.__new__`'s `TypeError` for an abstract class; their docstrings |
| `_codecs` (`_pystachy_codecs`) | `Modules/_codecsmodule.c`, `Objects/unicodeobject.c`, `Objects/stringlib/codecs.h` | The UTF-8, Latin-1, ASCII and charmap codec functions, `encode()`, `decode()` and the error handler registry, with the C module's errors and messages; the other codecs raise `NotImplementedError` |
| `_struct` (`_pystachy_struct`) | `Modules/_struct.c`, `Objects/floatobject.c` | `calcsize()`, and the packing and unpacking of each item, which the compiler composes into `pack()`, `unpack()`, `unpack_from()` and `iter_unpack()` for a format it knows, with the C module's sizes, alignment, errors and messages and `PyFloat_Pack2()`'s rounding; `Struct`; their docstrings |
| `_thread` (`_pystachy_thread`) | `Modules/_threadmodule.c`, `Python/pytime.c` | Locks and reentrant locks for one thread, with `acquire()`'s checks of its arguments and the C module's errors and messages; thread identities and handles, `stack_size()`, `interrupt_main()`, `exit()`; their docstrings |
| `unicodedata` (`_pystachy_unicodedata`) | `Modules/unicodedata.c`, `Tools/unicode/makeunicodedata.py` | Every function and `ucd_3_2_0`, with the C module's errors and messages, on the tables that `tools/unicodedata_tables.py` takes from CPython's `unicodedata`; their docstrings |
| `itertools` (`_pystachy_itertools`) | `Doc/library/itertools.rst` (SHA-256 `1c100cdb246d6281ba452bc230a9b05f4bc4838be3080e3e3b7a17cec8d728b1`), `Modules/itertoolsmodule.c` (SHA-256 `41d82be144617b20c4ae75a171e8cb65ed6e00f43cc3994340eea06d21a8cf6e`) | Every function of the C module as a generator, following the documentation's pure-Python equivalents, with the C types' argument checks, messages, order of reads, and the module's docstring; `tee()`'s shared links and `groupby()`'s shared state as the C types keep them |
| `_pystachy_iterators` | `Objects/listobject.c`, `tupleobject.c`, `unicodeobject.c`, `rangeobject.c`, `dictobject.c`, `setobject.c` | Iterator classes of `iter()` over builtin containers, with CPython's exhaustion and size-change checks and messages |

`re/_constants.py` retains upstream opcode/flag numbers. `tools/re_tables.py`
generates `re/_unicode.py` from CPython's Unicode functions, including group-name
identifiers, character classes, case mappings and `_casefix.py` exceptions.
These are substantial subset ports, rather than unchanged Python files.

## What the checks establish

`tests/lib_*.py` compares supported compiled paths with CPython through JIT and
AOT. `tests/errors/` checks unsupported inputs; `tests/deviations/` checks
intentional differences. Running an adapted module under CPython separately
checks that it remains compatible Python, including paths Pystachy does not use.

Historical upstream-suite checks recorded with the ports:

| Adapted module | Upstream suite run under CPython | Recorded result |
|---|---|---|
| `difflib` | `test_difflib` | 57 tests passed |
| `getopt` | `test_getopt` | 8 tests and doctest passed; translation-catalog tooling excluded |
| `heapq` | `test_heapq` | 51 tests passed |
| `io.StringIO` | `test_memoryio` StringIO cases | 29 of 39 passed, with `IntLike` replaced by int |
| `io.BytesIO` | `test_memoryio` BytesIO cases (`PyBytesIOTest`, and `CBytesIOTest`'s own) | 25 of 47 passed, with `IntLike` replaced by int; the others need `getbuffer()`, `readinto()`, `detach()`, pickling, `array` or buffer-protocol objects, or test a `TypeError` that Pystachy's types make a compile-time error |
| `textwrap` | `test_textwrap` | 66 tests passed |
| `string` | `test_string` | 39 tests passed, including 25 Template tests |
| `statistics` | `test_statistics` | All 401 tests passed, including a run with the ported `sumprod` |
| `urllib.parse` | `test_urlparse` | All 77 passed, with five upstream subtest skips |
| `urllib.parse` | `test_urllib` quoting/query classes | 28 of 29 passed; strict codec exception subclass differs |
| `html` | `test_html` | Both tests passed |
| `keyword` | `test_keyword` | All 11 tests passed |
| `shlex` | `test_shlex` | 43 of 44 passed; punctuation field is writable |
| `random` | `test_random` | 106 passed, two memory-limited skips; with `_pyrandom`, 96: nine need over 63 bits, one pickles `_random.Random` |
| `datetime` | `test_datetime`'s pure-Python cases | 1209 of 1775 passed, 27 skipped; the others need local time, pickling, hashing, subclass construction, `NotImplemented` reflection, the `timezone.utc` singleton or dynamic argument types |
| `binascii` | `test_binascii`, with `_pystachy_binascii` as `binascii` | 72 of 93 passed and 17 skipped (Hypothesis and big-memory tests); the 4 `test_c_contiguity` cases need non-contiguous `memoryview` buffers |

These counts describe specific recorded checks of the adapted source under
CPython, not the number of APIs or upstream tests executed by the compiled
subset. Current test commands and CI coverage are in
[the testing guide](../docs/testing.md).

The deque and defaultdict reference at the same pinned CPython commit,
`Modules/_collectionsmodule.c`, has SHA-256
`02d5bcaea730fc7af1fed5f50f87eacad710022dbebb1efebbbd1737ec940cae`;
`Lib/collections/__init__.py` has
`f1bcb4869aeb72253315fcf04646eb3a87e7140afec65bda6500aa609fc2f641`, and
`Objects/odictobject.c` has
`bc7d7009221eed5d7be4124bfd5f9ff9cd05650a543fdc56e0a1da3bc330714a`.
`tests/lib_collections.py` and `tests/lib_collections_mutation.py` exercise compiled
queue operations, callback mutation and bounded repetition;
`tests/lib_collections_counter.py`, `_defaultdict.py`, `_ordereddict.py` and
`_reversed.py` the mappings and `reversed()`; `tests/lib_collections_namedtuple.py`,
`_methods.py` and `_mod.py` the namedtuple classes. Shlex's differential
upstream selection retains its three split/join table methods; HTML retains both
upstream methods, and keyword retains nine methods while excluding dynamic `exec`.
Test headers record source-test hashes and exclusions.

`tools/random_check.py` runs the adapted `lib/random.py` on CPython, with the C `_random`
and with `_pyrandom` in its place, and compares the values of every supported method with
CPython's `random` for 1,352 int, bool and float seeds. It also compares `_pyrandom`'s float
hash with `hash()` and the `lgamma` port with `math.lgamma()`. Its `--upstream DIR` option
runs the pinned `test_random` (SHA-256
`04ffe61561421e6cf3b85edcea3ebaca995e6a5def1267cf3562acbb3b9b1337`) and its `randv*.pck`
files from DIR on both generators, as recorded above.

`tools/codecs_check.py` runs `lib/_pystachy_codecs.py` on CPython and compares the results and
errors of 96,000 calls of its codec functions, with every error handler and on the decoding
tables of the standard library's table codecs, with those of the C module (`Modules/_codecsmodule.c`,
SHA-256 `bd2f762ac481caabd817f6b94de19f3788ae7635406d06770b7972aafad03632`, whose codecs are in
`Objects/unicodeobject.c`, SHA-256
`68a5618c520f5b348e9e2abe1a77688c4b0c1f377d86f79e3399b41b445c24ab`, and
`Objects/stringlib/codecs.h`, SHA-256
`d126faea1dcf3f3b19a256237e5e87bdaa006dbc5b26fb0b5267f9a1dcbab3b4`), and compares the 39
functions' signatures.

`tools/binascii_check.py` runs `lib/_pystachy_binascii.py` on CPython, compares the results and
errors of 420,000 calls of its functions, mostly at the edges of their inputs, with those of the C
module (`Modules/binascii.c`, SHA-256
`b5919586319f5e28f9a4c1754691908af77489aadcbde97ca1ca998af2fcd1d2`, whose hex separators are
`Python/pystrhex.c`'s, SHA-256 `7842f6d7d9b58bcbf10cbb24d29f6d1f36668e20f935689e197bbe0abdccd4ed`),
and compares their signatures. Its `--upstream DIR` option runs the pinned `test_binascii`
(SHA-256 `95648ecc7cd21319fd515090ef5c0c2e4a501d43409ffc3ce27f5f647e73c7d7`) on the port, as
recorded above.

`tools/struct_check.py` runs `lib/_pystachy_struct.py` on CPython and composes its functions
item by item as the compiler composes them, for 20,000 random formats, native and standard,
with values at the edges of the codes' ranges and beyond, signed zeros, subnormals, infinities,
NaNs and ties of rounding, cut and padded bytes, and offsets and buffers of every size. It
compares the bytes, values and errors of 100,000 calls, also of `calcsize()` with invalid
formats, with those of the C module (`Modules/_struct.c`, SHA-256
`851f2a21bdbf4432c2e525da31a68a8213f5a4341d90bb2a6857b84c1a73d8e6`, which packs floats with
`Objects/floatobject.c`'s `PyFloat_Pack2()`, `PyFloat_Pack4()` and `PyFloat_Pack8()`, SHA-256
`be9a74fef157cf6105de8ce3beedb5325f0b433ebd4c64e604aeb9ebf29394b1`), and compares the functions'
signatures and docstrings.

`tools/itertools_check.py` runs `lib/_pystachy_itertools.py` on CPython and compares it with the
C module (`Modules/itertoolsmodule.c`, SHA-256
`41d82be144617b20c4ae75a171e8cb65ed6e00f43cc3994340eea06d21a8cf6e`) for 40,000 random calls of
its twenty functions, over inputs that log their reads: the errors of the calls, the items and
errors as they are taken one at a time (interleaving `tee()`'s iterators and `groupby()`'s
groups), and the order in which the inputs are read, but for the reads that CPython's iterators
make after their inputs' end (`tests/deviations/lib_itertools_ended.py`).
`tests/upstream_itertools.py` adapts `Lib/test/test_itertools.py` (SHA-256
`b356e71312eaac265c7104c32176c5150ab06433754bcb25d6e0013f321ca1c9`); its header lists the
adopted and excluded cases.
`tools/thread_check.py` runs `lib/_pystachy_thread.py` on CPython and compares it with the C
module (`Modules/_threadmodule.c`, SHA-256
`2bda8f59c35c9939a45819471b248115284f4d74405c5f4172e65ee058d5bc70`, whose timeouts
`Python/pytime.c` converts, SHA-256
`d6c7c60fd1302f7fe665a27091764dfb5d0cf472f645e94c937971fb47683462`) for 20,000 random cases:
`acquire()` of unlocked and locked locks and reentrant locks, with blocking flags and int and
float timeouts at the edges of `PyTime_t`'s range, NaNs and infinities; a reentrant lock's counts,
also through `_release_save()` and `_acquire_restore()`; `stack_size()` and `interrupt_main()`.
With the functions' signatures and docstrings, that is 263,014 checks.

`tools/unicodedata_tables.py` asks CPython 3.13.16's `unicodedata` about every code point and
writes `lib/_pystachy_unicodedata_db.py` and `_pystachy_unicodedata_names.py`. The aliases, named
sequences and 3.2.0's corrected decompositions, which no function lists, come from Unicode
15.1.0's `NameAliases.txt` (SHA-256
`fbf0e640bab36e165c4da5b6a98bdd963fcb4f923b5097f26f6f7f18b9678698`), `NamedSequences.txt`
(`7700f03419912fc58c26962b6252e2fcac135240a26925440aff6a4c8b714795`) and
`NormalizationCorrections.txt`
(`c5b44a452cec45b1907f9b6b255f57492ccfb813bcc56fefdef0204493634be7`), each checked against
CPython's `lookup()` and `ucd_3_2_0.normalize()`. `tools/unicodedata_check.py` runs
`lib/_pystachy_unicodedata.py` on CPython and compares it with the C module
(`Modules/unicodedata.c`, SHA-256
`d44b25f8269744833467d512a6c6a0c7095818e2d2e058290318ef5d9ffa0893`, whose tables
`Tools/unicode/makeunicodedata.py` makes, SHA-256
`6c4a119ec7e0cb029407c205b948aaee1115506b11af44c9a79644afd4726828`): every function of every
code point, in both versions; `lookup()` of every name, in upper and lower case, alias, named
sequence and derived name, and of 4,000 malformed ones; `normalize()` and `is_normalized()` of
50,000 random strings in the four forms of both versions; and the functions' signatures and
docstrings: 3,515,917 checks.

Regex validation also includes `tests/upstream_re_*.py`, deterministic
`tools/re_fuzz.py` comparisons against CPython, and `tools/re_probe.py` checks of
matcher-entry/context counts. Cache, Unicode-range, whitespace and character-class
regressions have dedicated `tests/lib_*` cases. Time measurements are advisory;
see [caching measurements](../docs/caching.md).

CPython-derived code and docstrings are used under the PSF License Version 2.
See [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES).


The HTML parser probe pins CPython commit `cbc944f4bc59639a444dd971c737788ba2283a91`.
`tests/upstream_html_parser.py` retains complete assertion sets from 45 upstream
methods, with helper/type adaptations and excluded methods disclosed in its header.
`tests/lib_html_parser.py` adds RAWTEXT/RCDATA, buffering, lifecycle and inheritance
checks. Native results must be reported separately from CPython-hosted checks;
see [the probe record](../docs/html-parser-probe.md).
