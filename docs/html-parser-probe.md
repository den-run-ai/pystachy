# Incremental HTML parser probe

This draft tests the compatibility benefit of ordinary single inheritance from
#379 by adapting CPython's `HTMLParser(ParserBase)` hierarchy. It uses the HTML
helpers and entity table from #378 verbatim. No compiler changes or experimental
#382 flags are required.

## Scope and adaptations

The parser retains the upstream scanning, buffering and callback algorithms.
Interfaces gain annotations, fields initialized by `reset` are first declared in
constructors, and required regex groups gain explicit optional-value assertions.
Attributes keep the upstream missing-value contract: `list[tuple[str, str | None]]`.
The private start-tag-text field uses its original mangled spelling explicitly.
The internal base keeps its imported `re` name and omits the abstract class-object
constructor guard. Unused legacy SGML methods stay upstream and are not claimed
as compiled APIs.

Supported probes cover incremental `feed`, EOF `close`, lifecycle `reset`,
`get_starttag_text`, ASCII `getpos`, subclass callbacks and base-typed receivers.
They include declarations, comments, processing instructions, malformed/partial
markup, named/numeric references, attributes, RAWTEXT, RCDATA, `scripting`,
plaintext and Unicode text. This is an HTML tokenizer with callbacks, as upstream
is; it is not a DOM builder or a proof of support for BeautifulSoup or other PyPI
packages.

## Boundaries

- Native `getpos` column offsets count UTF-8 bytes rather than Unicode characters.
- Native tag and attribute names use ASCII-only case conversion. Non-ASCII
  uppercase name characters remain uppercase.
- Typed subclass constructors/callbacks must follow the supported inheritance
  contract; multiple/generic inheritance and dynamic attributes are unavailable.
- Direct `_markupbase.ParserBase` construction is permitted by the port, whereas
  CPython raises RuntimeError. `_markupbase` is not a public supported API.
- Legacy SGML declaration helpers, arbitrary runtime monkey-patching and
  reflection are outside the validated surface.

The three deviation programs record the column, case-conversion and base-guard
boundaries explicitly.

## Provenance

CPython 3.13.16 commit `cbc944f4bc59639a444dd971c737788ba2283a91`:

| Original file | SHA-256 |
|---|---|
| `Lib/html/parser.py` | `4274e9112adf3fa57c7f9afa7c9b5c631456b18b7403cc627cc5027d02cdd2ae` |
| `Lib/_markupbase.py` | `cb14dd6f2e2439eb70b806cd49d19911363d424c2b6b9f4b73c9c08022d47030` |
| `Lib/test/test_htmlparser.py` | `e472b02e738497694caa519a5ccf9b9ae84442cfe3d027ec760f533460a1c175` |

All source adaptations carry `# Pystachy port:` comments. HTML helper/entity
provenance is in [lib/provenance.md](../lib/provenance.md). The PSF license applies
as recorded in [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES).

## Validation and reproduction

`tests/upstream_html_parser.py` preserves complete assertion sets from **45**
upstream test methods. It replaces unittest machinery and heterogeneous event
records with standalone assertions and fixed-shape typed records; adjacent data
normalization matches the upstream collector. Each string input is fed whole and
one indexing unit at a time; explicit fragment lists preserve their boundaries.
Its header lists exclusions. `tests/lib_html_parser.py` covers the omitted parser
modes, lifecycle, default conversion and inheritance dispatch.

Local validation uses CPython 3.12.14 with the pinned parser/base sources as the
oracle. Both programs pass against the upstream and adapted sources; an independent
132-case source comparison also passes. All five test/deviation programs compile
with Pystachy's internal IR verifier enabled. LLVM is unavailable in the local
workspace, so native JIT/AOT, self-hosting and GC-stress execution is delegated to
the repository's existing CI matrix. Native results must be read from CI and kept
separate from hosted source/IR results. No performance claim is made.

The tests live in the normal corpus, so the existing CI matrix exercises them:

```sh
PYSTACHY_IRCHECK=1 python3 pystachy.py ir tests/upstream_html_parser.py -o build/html-parser.ll
PYTHONPATH=lib python3 tests/upstream_html_parser.py
PYTHONPATH=lib python3 tests/lib_html_parser.py
make test FILES="tests/upstream_html_parser.py tests/lib_html_parser.py tests/deviations/lib_html_parser_positions.py tests/deviations/lib_html_parser_names.py tests/deviations/lib_markupbase_constructor.py"
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy "jit aot" tests/upstream_html_parser.py tests/lib_html_parser.py
```

The local probe began from main `c9d1e5964a40972faebac580ca41d0bd59d4f2a2`.
The copied HTML helpers match #378 head `11502b5b7ff14343fdc883d32b0b7c00f4daad12`;
if that PR merges first, those identical additions disappear from this PR's diff.
