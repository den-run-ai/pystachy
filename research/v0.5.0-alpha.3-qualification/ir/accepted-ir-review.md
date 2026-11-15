# Independent accepted-IR disposition

Baseline: `80490143498d149d407343ba1cb7aedb1db2d2c5`. Candidate: `b0bda81ec2b9954c3c5e0f658c051439126a5c22` (tree `e027b37c888326e3d8a3e8b89522a6b397dcb86d`).

**Result: all 379 accepted-to-accepted IR differences are accounted for; no blocking source/IR finding or unexplained semantic change was identified.** This conclusion is limited to the retained IR comparison. It does not grant runtime or Lean proof, and does not waive proof-adapter errors found by other release gates.

| Disposition | Cases |
| --- | ---: |
| verified-checkout-path-literals-only | 196 |
| unused-class-type-declarations-only | 32 |
| unused-numeric-identity-capture | 3 |
| runtime-tuple-header-layout | 43 |
| unreferenced-reflected-specialization-removal | 6 |
| known-nonnull-comparison-specialization | 1 |
| enum-comparison-dispatch | 19 |
| fixed-constructor-admission-and-layout | 12 |
| enum-field-layout | 7 |
| numeric-container-identity-companions | 11 |
| literal-tuple-item-identity | 2 |
| numeric-tuple-search-identity | 1 |
| numeric-generator-identity-channel | 31 |
| reflected-specialization-name-only | 1 |
| union-reference-identity-before-equality | 1 |
| datetime-comment-only-source-and-path | 3 |
| toml-tuple-null-guards-and-layout | 8 |
| unused-numeric-identity-capture-and-constants | 1 |
| fixed-constructor-and-runtime-tuple-layout | 1 |

## Evidence and review boundaries

- Read-only independent review of retained raw old/new IR and source integration. No comparison predicate, oracle, production input or source was edited.
- 196 path-only cases require exact validated LLVM literal replacement and equal referenced library bytes. Three changed datetime source files instead have a separately verified comment-only full AST identity.
- 32 unused-type cases require whole IR equality outside only the changed, unreferenced declaration lines.
- All 151 remaining cases have explicit semantic dispositions, complete function/global inventories and retained raw diff hashes. Per-function bijective local names and exact literal/metadata contents aid reading; opcode/operand/control-flow differences remain reviewed changes.
- Operation views that replace locals by %VAR are reading aids only, never equality proofs or acceptance criteria.
- Prior enum evidence is used only for 26 individually verified whole-IR matches; 22 baseline/candidate pairs match the prior pair, and four additional broad-baseline deltas are separately reviewed.
- Unused numeric calls, explicit constructor/name mappings, VTuple layout changes and source AST checks have bounded dedicated evidence, never blanket normalization.

The complete per-case reasons, exact source and raw-result hashes, changed function/global inventory, and bounded structural checks are in `accepted-ir-review.json`. `original-input-disposition.json` independently covers the old versions of changed/removed inputs and their import helpers. No raw case was deleted or rewritten.

## Per-case disposition

### 4: tests/programs/apps/byte_bpe.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 6: tests/programs/apps/example_column.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 11: tests/programs/apps/example_linediff.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 12: tests/programs/apps/example_mailmerge.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 14: tests/programs/apps/example_montecarlo.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 21: tests/programs/apps/example_route.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 22: tests/programs/apps/example_route_empty.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 23: tests/programs/apps/example_suggest.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 25: tests/programs/apps/example_urlstats.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 58: tests/programs/apps/port_json_repair_cli.py

**unused-numeric-identity-capture.** Literal numeric identity capture now emits the explicitly listed pys_dyn_int(0) calls in regex parsing helpers. Each result has exactly one SSA occurrence, its definition, and is unused. The complete function is identical after only those recorded dead calls and bijective local/literal/metadata names are accounted for. No value, comparison, branch or externally consumed identity changes.

### 77: tests/programs/apps/port_roman_cli.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 78: tests/programs/apps/port_roman_convert.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 79: tests/programs/apps/port_roman_validate.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 80: tests/programs/apps/port_sgp4_api.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 81: tests/programs/apps/port_sgp4_verify.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 83: tests/programs/apps/port_sortedcontainers_api.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 84: tests/programs/apps/port_sortedcontainers_index.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 85: tests/programs/apps/port_sqids_blocklist.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 86: tests/programs/apps/port_sqids_encode.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 87: tests/programs/apps/port_tomli_w_ini2toml.py

**unreferenced-reflected-specialization-removal.** Only unused mappingproxy.__ror__ specializations disappear, together with now-unused runtime declarations where applicable. Every removed symbol has zero references outside the removed definitions in the old module. All retained function bodies match after exact literal/metadata resolution. This follows lazy admission of reflected methods and removes no executed call.

### 88: tests/programs/apps/port_tomli_w_tables.py

**unreferenced-reflected-specialization-removal.** Only unused mappingproxy.__ror__ specializations disappear, together with now-unused runtime declarations where applicable. Every removed symbol has zero references outside the removed definitions in the old module. All retained function bodies match after exact literal/metadata resolution. This follows lazy admission of reflected methods and removes no executed call.

### 89: tests/programs/apps/port_tomli_w_values.py

**unreferenced-reflected-specialization-removal.** Only unused mappingproxy.__ror__ specializations disappear, together with now-unused runtime declarations where applicable. Every removed symbol has zero references outside the removed definitions in the old module. All retained function bodies match after exact literal/metadata resolution. This follows lazy admission of reflected methods and removes no executed call.

### 110: tests/programs/classes/class_field_metadata.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 131: tests/programs/classes/cmp_notimplemented_direct.py

**known-nonnull-comparison-specialization.** The V operands at the affected direct comparison calls are newly constructed and therefore known nonnull. Specialized __eq__ and __lt__ bodies drop unreachable None receiver guards, and main drops the corresponding constant-false NoneType exception branch. The seven removed strings belong only to those unreachable branches; custom comparison method order and accepting results remain.

### 136: tests/programs/classes/cmp_notimplemented_enum_search.py

**enum-comparison-dispatch.** Lenient-search regression: optional primitives split before enum dispatch; nonmatching narrow-annotation pairs remain false, and StrEnum construction includes the hidden slot. This case has separate before/after CPython output parity evidence. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline differs from the prior baseline, so its additional pre-repair delta was separately retained and reviewed. Earlier alpha.2-to-pre-repair changes are also reviewed: optional primitive tuple-search operands split around None before class dispatch, and the previously constant-false branch is represented by guarded optional paths. The final enum stage preserves lenient narrow-annotation search and correct scalar fallback.

### 160: tests/programs/classes/constructor_fixed_lazy.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. Used allocation moves before materializing the literal [1, 2] argument. The same list is initialized before the same initializer call; initializer and string methods are otherwise identical. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 161: tests/programs/classes/constructor_fixed_lazy_base.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 164: tests/programs/classes/constructor_fixed_module.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. Count allocation moves before literal argument-list materialization. Stores, initializer calls and reader methods retain their order and values. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 166: tests/programs/classes/constructor_fixed_store_nested.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. Nested fixed-field stores and constructor methods are exactly identical after the explicit class/type/function-name map. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 167: tests/programs/classes/constructor_fixed_store_order.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. Fixed-field store-order methods are exactly identical after the explicit class/type/function-name map. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 168: tests/programs/classes/constructor_fixed_store_sequence.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. Fixed sequence-store constructor methods are exactly identical after the explicit class/type/function-name map. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 169: tests/programs/classes/constructor_fixed_untyped.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. The untyped fixed-constructor methods are exactly identical after the explicit class/type/function-name map. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 215: tests/programs/classes/field_helper_return.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 300: tests/programs/classes/private_name_intrinsics.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 327: tests/programs/classes/tuple_reference_union_identity.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 334: tests/programs/classes/tuple_search_union_eq.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 335: tests/programs/classes/tuple_search_union_kinds.py

**enum-comparison-dispatch.** Existing class-union tuple search: only enum arm f.en changes behavior; inherited IntEnum.__eq__ calls become nonnull immutable int field loads and icmp; removed IntEnum eq helpers and corresponding error strings. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 412: tests/programs/containers/paired_comparison_shapes.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 414: tests/programs/containers/range_value.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 431: tests/programs/containers/slice_step.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 441: tests/programs/containers/tuple_constant_identity.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 448: tests/programs/containers/tuple_materialization.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 452: tests/programs/containers/tuple_runtime_coercions.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 453: tests/programs/containers/tuple_runtime_concat.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 454: tests/programs/containers/tuple_runtime_concat_none.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 455: tests/programs/containers/tuple_runtime_lifetime.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 456: tests/programs/containers/tuple_runtime_operations.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 457: tests/programs/containers/tuple_runtime_optional.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 459: tests/programs/containers/tuple_runtime_regex.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 460: tests/programs/containers/tuple_runtime_snapshot.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 463: tests/programs/containers/tuple_slice_variadic.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 512: tests/programs/exceptions/exc_class_exit_enum.py

**enum-field-layout.** Reviewed full raw diff: StrEnum/_StrMixin gain the hidden original-string ptr, existing mutable _value_/assigned-bit GEP indices shift 3/4 to 4/5, and corresponding TBAA field offsets shift 24/32 to 32/40. No unrelated instruction or diagnostic change. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 556: tests/programs/exceptions/exc_exit_enum_stored.py

**enum-field-layout.** Reviewed full raw diff: StrEnum/_StrMixin gain the hidden original-string ptr, existing mutable _value_/assigned-bit GEP indices shift 3/4 to 4/5, and corresponding TBAA field offsets shift 24/32 to 32/40. No unrelated instruction or diagnostic change. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 618: tests/programs/exceptions/exit_enum_member.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 619: tests/programs/exceptions/exit_enum_member_caught.py

**enum-comparison-dispatch.** Existing caught enum exits: IntFlag object eq/order helpers use immutable integer slot instead of inherited library methods; StrEnum formatting accesses shift with layout; flag formatting string IDs renumber only. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 620: tests/programs/exceptions/exit_enum_member_message.py

**enum-field-layout.** Reviewed full raw diff: StrEnum/_StrMixin gain the hidden original-string ptr, existing mutable _value_/assigned-bit GEP indices shift 3/4 to 4/5, and corresponding TBAA field offsets shift 24/32 to 32/40. No unrelated instruction or diagnostic change. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 621: tests/programs/exceptions/exit_enum_member_optional.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 622: tests/programs/exceptions/exit_enum_nonint_protocol.py

**enum-field-layout.** Reviewed full raw diff: StrEnum/_StrMixin gain the hidden original-string ptr, existing mutable _value_/assigned-bit GEP indices shift 3/4 to 4/5, and corresponding TBAA field offsets shift 24/32 to 32/40. No unrelated instruction or diagnostic change. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 623: tests/programs/exceptions/exit_enum_stored_mutated.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 624: tests/programs/exceptions/exit_enum_stored_promoting.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 625: tests/programs/exceptions/exit_enum_stored_reflection.py

**enum-comparison-dispatch.** Existing enum reflection: f.probe changes only StrEnum/_StrMixin assigned-bit field offsets; IntFlag eq/order helpers use immutable payload, related unused library helpers disappear and string IDs renumber. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline differs from the prior baseline, so its additional pre-repair delta was separately retained and reviewed. Earlier alpha.2-to-pre-repair changes add eleven reflected integer dunder names (__radd__, __rand__, __rfloordiv__, __rlshift__, __rmod__, __rmul__, __ror__, __rrshift__, __rsub__, __rtruediv__, __rxor__) to IntEnum/_IntMixin/IntFlag and concrete numeric enum reflection tables. Table counts and entry indices increase consistently; reflected method availability is intentional.

### 626: tests/programs/exceptions/exit_enum_stored_status.py

**enum-field-layout.** Reviewed full raw diff: StrEnum/_StrMixin gain the hidden original-string ptr, existing mutable _value_/assigned-bit GEP indices shift 3/4 to 4/5, and corresponding TBAA field offsets shift 24/32 to 32/40. No unrelated instruction or diagnostic change. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 627: tests/programs/exceptions/exit_enum_stored_zero.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 628: tests/programs/exceptions/exit_intflag_stored_mutated.py

**enum-comparison-dispatch.** Existing mutated IntFlag exit: object eq/order helpers replace IntFlag library dispatch with immutable integer loads; StrEnum layout offsets shift; exit source logic unchanged. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 629: tests/programs/exceptions/exit_intflag_stored_zero.py

**enum-comparison-dispatch.** Existing zero IntFlag exit: object eq/order helpers replace library dispatch with immutable integer loads; related unused comparison helper bodies/error strings disappear and flag-format strings renumber. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 688: tests/programs/generators/iter_review.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 818: tests/programs/imports/import_alias_ready_struct.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 823: tests/programs/imports/import_builtin_exc_alias_attr.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 824: tests/programs/imports/import_builtin_submodule.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 828: tests/programs/imports/import_conditional_closures.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 830: tests/programs/imports/import_conditional_function.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 831: tests/programs/imports/import_conditional_nested_def.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 836: tests/programs/imports/import_module_attr_same_name.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 843: tests/programs/imports/module_doc.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 998: tests/programs/inference/dynany_cmp_nested_tuples.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1012: tests/programs/inference/dynany_cmp_union_fields.py

**numeric-container-identity-companions.** The two float tuple items gain explicit retained identity constants for 1.0 and 2.0, the runtime tuple header grows by one word, and set_identity stores the corresponding boxes. Union-field payload values and comparison alternatives are unchanged. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1041: tests/programs/inference/dynany_eq_annotated_tuple.py

**literal-tuple-item-identity.** Identity boxes are produced from literal integers 99 and 0 instead of loading them from @tc.0. That unchanged immutable tuple constant contains exactly 99 and 0; raw tuple values, payload loads and the annotated equality method are otherwise unchanged. This retains the identity associated with source literal items.

### 1043: tests/programs/inference/dynany_eq_datetime.py

**numeric-tuple-search-identity.** datetime._check_time_fields membership of fold in (0,1) gains the numeric item-identity fast path before its existing equality checks. Both literal values and all validation/return branches remain. The identity fast path is required for general tuple search and is harmless for these two integers.

### 1054: tests/programs/inference/dynany_generator_boxing.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. The generator expression, numbers and dyn.next carry integer identity; main reads the companion before dynamic boxing.

### 1055: tests/programs/inference/dynany_generator_channel_protocol.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. The typed integers channel stores the added companion; the boxed forwarding channel snapshots it before converting to Any. Send/return protocol fields retain their original slots.

### 1057: tests/programs/inference/dynany_generator_channel_values.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. The typed/boxed channel conversions retain the integer companion across yield-from; checked conversions still perform their existing range/type checks.

### 1060: tests/programs/inference/dynany_generator_exceptions.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Broken, guarded and stop_inside keep their exception/StopIteration paths; only their yielded numeric payload companions and dyn.next boxing change.

### 1061: tests/programs/inference/dynany_generator_return_none.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Explicit, implicit, inferred and collected generators keep their None return semantics and add only numeric-yield identity plumbing.

### 1062: tests/programs/inference/dynany_generator_send_none.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. The send(None) generator retains its protocol state and send handling while yielding payload plus nullable identity; main snapshots that identity.

### 1063: tests/programs/inference/dynany_generator_send_protocol.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Delegated and source protocol generators forward raw value and identity together; send/throw/close control paths and existing cleanup remain.

### 1070: tests/programs/inference/dynany_graph.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1100: tests/programs/inference/dynany_identity_generator.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Float and integer alias generators append slot 5; dyn.next and forwarding channels preserve the yielded boxes. check snapshots each yield before another resume; next(default) uses parallel payload and identity phis; unpack/loop assignment updates identity version only when the object changes. List materialization preserves each yielded identity. The large textual moves in the operation view come from repeated branch sequences, not a new order of source iterator consumption.

### 1101: tests/programs/inference/dynany_identity_generator_fresh.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Alias and overwritten generators store the alias box for aliased yields and null for fresh computed values. Every consumer snapshots the box before another resume. Repeated assignment, tuple unpacking and loops keep separate boxes/version counters for each result; overwriting an earlier promise does not mutate a previously saved identity.

### 1102: tests/programs/inference/dynany_identity_generator_protocol.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Protocol source/typed/dynamic channels use the added identity word after the seven existing protocol words. Raw yields, sends, return values and cleanup are retained while conversions snapshot identity.

### 1103: tests/programs/inference/dynany_identity_generator_scope.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Scope-specific integer/float generators and dyn.next preserve companions without converting unrelated non-identity scopes to a different payload ABI.

### 1122: tests/programs/inference/dynany_identity_optional_container_effects.py

**numeric-container-identity-companions.** Optional-float list and VTuple effects now capture each value and its box before later arguments/callbacks can rebind or mutate the source. Mutators use kind 10. Search queries keep separate item and query descriptors (including A) rather than prematurely coercing the query to optional float. Query.__eq__ mutates payload and identity together. The added recursion-enter/restore surrounds callback-capable comparison paths. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1123: tests/programs/inference/dynany_identity_optional_container_imports.py

**numeric-container-identity-companions.** Imported make/replace/read and list-to-VTuple conversion preserve optional-float boxes using kind 10. None remains the singleton, cross-module mutation updates both payload and identity, and reads return the stored box instead of freshly boxing the numeric payload. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1124: tests/programs/inference/dynany_identity_optional_lists.py

**numeric-container-identity-companions.** Optional-int/float list append, set, insert, pop, remove, count, index, iteration, copy, slice, repeat and clear preserve item identities. Kinds 9 and 10 distinguish nullable payloads; searches pass separate optional/string/float query descriptors, so cross-kind equality and shared-NaN identity are retained. Pop returns the saved dynamic box and reconstructs any typed optional representation separately. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1125: tests/programs/inference/dynany_identity_optional_tuple.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1126: tests/programs/inference/dynany_identity_optional_vtuples.py

**numeric-container-identity-companions.** Optional numeric VTuples reserve the identity header and set kinds 9/10 on all literal elements including the None singleton. Construction, list conversion, slicing, concatenation, widening, unpacking and reads preserve or share the same item boxes while keeping their own container storage. Nullable reads retain the raw optional payload and attach the saved identity; plain numeric reads unbox the saved identity. Fresh optional values are boxed once at the capture boundary. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1146: tests/programs/inference/dynany_identity_vtuple_effects.py

**numeric-container-identity-companions.** VTuple construction captures numeric boxes before later arguments mutate/rebind inputs. Generator consumption snapshots identities, and tuple comparison uses identity before equality for the same numeric object. Payload evaluation order remains the source order, and copies retain shared element identity rather than wrapper identity. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1147: tests/programs/inference/dynany_identity_vtuples.py

**numeric-container-identity-companions.** Runtime tuple materialization, copy/slice/list conversion and item access preserve stored numeric identities, including shared NaN, positive/negative zero and static literal boxes. Fresh elements can lazily materialize their own boxes; separate equal float objects are not merged by numeric equality. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1158: tests/programs/inference/dynany_iter_errors.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. In addition to generator companions, the optional-int list path uses identity kind 9 for append/get, preserving the None singleton and saved integer boxes. Existing bad-iterator/error branches remain.

### 1159: tests/programs/inference/dynany_iter_hint_index.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. DynamicHint, NullableHint, StaticBadHint and UnionHint iterators add integer companions; their length-hint validation and error behavior remain.

### 1160: tests/programs/inference/dynany_iter_key.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Numbers.__iter__ and dyn.next carry the existing yielded integer identity; key behavior is unchanged.

### 1163: tests/programs/inference/dynany_iter_sequence_fast.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Huge and InvalidHint iterators add integer companions; sequence-fast and invalid-hint control flow remains.

### 1166: tests/programs/inference/dynany_iterator_type_identity.py

**literal-tuple-item-identity.** Identity boxes are produced from literal integers 1 and 2 instead of loading them from @tc.0. The unchanged tuple constant contains those exact values. Iterator descriptor identity logic and other functions are unchanged.

### 1172: tests/programs/inference/dynany_json_bigints_raw.py

**unused-numeric-identity-capture.** Literal numeric identity capture now emits the explicitly listed pys_dyn_int(0) calls in regex parsing helpers. Each result has exactly one SSA occurrence, its definition, and is unused. The complete function is identical after only those recorded dead calls and bijective local/literal/metadata names are accounted for. No value, comparison, branch or externally consumed identity changes.

### 1176: tests/programs/inference/dynany_json_raw_decode.py

**unused-numeric-identity-capture.** Literal numeric identity capture now emits the explicitly listed pys_dyn_int(0) calls in regex parsing helpers. Each result has exactly one SSA occurrence, its definition, and is unused. The complete function is identical after only those recorded dead calls and bijective local/literal/metadata names are accounted for. No value, comparison, branch or externally consumed identity changes.

### 1211: tests/programs/inference/dynany_native_int_list_dormant.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1236: tests/programs/inference/dynany_reflected.py

**reflected-specialization-name-only.** The two Box.__radd__ specializations gain the .1 name suffix and their callers change accordingly. All 53 function bodies are exactly identical after only the two explicit symbol mappings, bijective local names and exact literal/metadata resolution. This is a verified specialization rename, not a behavior normalization.

### 1239: tests/programs/inference/dynany_slice_errors.py

**numeric-container-identity-companions.** The slice-error fixture changes only runtime tuple header sizing and three set_identity calls for the existing literal integers 1, 2 and 3. Slice bounds, step validation and exception branches remain. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1250: tests/programs/inference/dynany_sum_compensated.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. stream yields floating payload plus identity and its consumer updates local identity counters accordingly. The compensated-sum arithmetic and iteration order are unchanged.

### 1258: tests/programs/inference/dynany_type_is_unopted.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. The imported count generator and dyn.next add identity companions. The tuple value identity uses the verified literal 1. The new dyn.sametype wrapper in this exact module only calls pys_dyn_same_type and returns whether its result is nonzero; no extra class alternative is emitted here, and negated callers use xor true.

### 1262: tests/programs/inference/dynany_vtuple_materialization.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1266: tests/programs/inference/dynany_zip_item_order.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. The typed and side-effecting writing generators preserve payload order and add identity snapshots for dyn.next; zip item acquisition remains in its original order.

### 1277: tests/programs/inference/mixed_union_equality.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1296: tests/programs/inference/reference_union_streams.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1321: tests/programs/inference/union_object_identity.py

**union-reference-identity-before-equality.** Membership/count of union-valued tuple elements now requires matching union alternative tag 3 before comparing the underlying list payload pointers for identity. It does not compare union wrapper addresses as object identity. The original pys_eq fallback remains for unequal identities and all other alternatives, preserving callback behavior while accepting identical reference objects before equality.

### 1495: tests/programs/language/walrus.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1530: tests/programs/library/lib_argparse_argv.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1531: tests/programs/library/lib_argparse_choice_error.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1532: tests/programs/library/lib_argparse_conversion.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1533: tests/programs/library/lib_argparse_conversion_order.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1534: tests/programs/library/lib_argparse_dest.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1535: tests/programs/library/lib_argparse_dormant.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1536: tests/programs/library/lib_argparse_equal_schemas.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1537: tests/programs/library/lib_argparse_help.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1538: tests/programs/library/lib_argparse_missing_value.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1539: tests/programs/library/lib_argparse_namespace.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1540: tests/programs/library/lib_argparse_nargs.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1541: tests/programs/library/lib_argparse_numeric_choices.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1542: tests/programs/library/lib_argparse_python_int.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1543: tests/programs/library/lib_argparse_python_int_eq.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1544: tests/programs/library/lib_argparse_required.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1545: tests/programs/library/lib_argparse_schema_builtin_names.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1546: tests/programs/library/lib_argparse_schema_numeric_choices.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1547: tests/programs/library/lib_argparse_scopes.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1548: tests/programs/library/lib_argparse_shadow.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1549: tests/programs/library/lib_argparse_token_abbrev.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1550: tests/programs/library/lib_argparse_token_unicode.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1551: tests/programs/library/lib_argparse_type_error.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1552: tests/programs/library/lib_argparse_unknown.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1553: tests/programs/library/lib_argparse_version.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1558: tests/programs/library/lib_bisect.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1576: tests/programs/library/lib_copy.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1577: tests/programs/library/lib_copy_any.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1585: tests/programs/library/lib_copy_native_any.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1586: tests/programs/library/lib_copy_native_any_promote.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1590: tests/programs/library/lib_datetime_datetime.py

**datetime-comment-only-source-and-path.** Whole IR is identical after the validated checkout-home literal replacement. datetime.py bytes do differ, so this is deliberately not classified as unchanged-library path-only: its full parsed AST is identical and the retained source diff contains only the reflected-timedelta comments. No instruction or diagnostic change remains.

### 1594: tests/programs/library/lib_datetime_time.py

**datetime-comment-only-source-and-path.** Whole IR is identical after the validated checkout-home literal replacement. datetime.py bytes do differ, so this is deliberately not classified as unchanged-library path-only: its full parsed AST is identical and the retained source diff contains only the reflected-timedelta comments. No instruction or diagnostic change remains.

### 1605: tests/programs/library/lib_difflib.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1606: tests/programs/library/lib_difflib_grouped.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1607: tests/programs/library/lib_difflib_unified.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1608: tests/programs/library/lib_enum.py

**enum-comparison-dispatch.** Existing broad enum library program: main comparisons and Num object eq/order helpers replace inherited scalar methods with immutable-payload comparisons; StrEnum methods and lookup retain mutable-value access at shifted fields. Planet.lightest and other non-scalar repr/str helpers have identical bodies after exact constant/metadata resolution. Uncalled inherited comparison specializations disappear. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline differs from the prior baseline, so its additional pre-repair delta was separately retained and reviewed. Earlier alpha.2-to-pre-repair changes remove two uncalled mappingproxy.__ror__ specializations and their now-unused dict-copy/update declarations; no retained call references those removed methods.

### 1609: tests/programs/library/lib_enum_any.py

**enum-comparison-dispatch.** The universal Enum helpers emit comparisons for imported enum classes, even though this program boxes plain Color members and Num.ONE.value as an int. o.eq.enum$Enum, o.ne.enum$Enum and o.cmp.enum$Enum replace inherited IntEnum/IntFlag/StrEnum method calls by tag-guarded immutable payload loads and accepting scalar comparisons. IntEnum/_IntMixin/Num use integer slot3, IntFlag uses slot6 in this dynamic layout, and StrEnum/_StrMixin use hidden string slot3. Eq/ne identity and unsupported ordering arms are retained. The 404 ordering error arms have identical literal messages in identical order. Inherited helpers no longer called by these stages disappear. The four StrEnum hash/value-repr methods only shift mutable _value_ and assigned-bit access 3/4 to4/5. Other repr/hash changes are only identical string/TBAA definitions renumbering. One import-error library path uses the candidate lib home. User main.init and show bodies are byte-identical. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1610: tests/programs/library/lib_enum_base_lookup.py

**enum-comparison-dispatch.** Base Enum lookup and membership compile alternatives for the imported enum hierarchy. Only numeric enum equality alternatives in EnumType.__call__/__contains__ replace inherited IntEnum/IntFlag methods with immutable integer comparisons. StrEnum value-repr accesses shift fields. User main, plain Enum repr/name logic and virtual dispatch are unchanged after literal/metadata renumbering. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1611: tests/programs/library/lib_enum_flag.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1612: tests/programs/library/lib_enum_flag_bits.py

**enum-comparison-dispatch.** Keep IntFlag object eq/order helpers use the immutable integer payload. Inherited IntFlag scalar comparison methods and the unused _int_of specialization disappear. CompositeOnly plain Flag ordering and _flag_bin formatting are identical after resolving renumbered literals. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1613: tests/programs/library/lib_enum_flag_numeric_lookup.py

**enum-comparison-dispatch.** I IntFlag object eq/order helpers replace inherited scalar method calls with immutable integer comparisons. Removed helpers are the now-unused inherited IntFlag comparisons/_int_of. Flag formatting is identical after literal resolution. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1614: tests/programs/library/lib_enum_flag_width.py

**enum-comparison-dispatch.** Dense, Sparse and Small IntFlag object eq/order helpers use immutable integer slots. Corresponding inherited methods/_int_of specializations disappear. Strict plain Flag ordering, all Flag repr methods and _flag_bin retain identical bodies after literal/metadata resolution. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1615: tests/programs/library/lib_enum_format_str.py

**enum-comparison-dispatch.** StrEnum formatting/value methods shift mutable-value fields and constructors initialize the new hidden original-string slot. Perm IntFlag object eq/order helpers use immutable integer slots. Flag repr/_flag_bin changes are only renumbered identical literals. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1616: tests/programs/library/lib_enum_import.py

**enum-comparison-dispatch.** Imported Weight IntEnum comparisons in main and object eq/order helpers use immutable integer slots. The remaining arithmetic _int_of specialization is exactly old .2 renamed to new .1, with its __add__ caller updated; arithmetic body is otherwise identical. Color/Item repr and lookup helpers differ only in identical literal/metadata IDs. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1618: tests/programs/library/lib_enum_intflag.py

**enum-comparison-dispatch.** Main numeric enum comparisons and I IntFlag object eq/order helpers use immutable scalar comparisons. Name/iteration/repr and plain P/Q Flag helpers only have literal renumbering. Remaining arithmetic _int_of is exactly old .3 renamed to new .2 and its __add__ call updates accordingly; no arithmetic behavior change. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1619: tests/programs/library/lib_enum_missing.py

**enum-field-layout.** StrEnum Color gains the immutable string slot; its two constructors store the same initial string in the hidden slot, and mutable value/assigned fields shift 3/4 to 4/5 with corresponding TBAA offsets. All 38 function bodies are otherwise identical after exact expected layout changes and bijective SSA/metadata resolution. Evidence: layout-only-review-evidence.json. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1620: tests/programs/library/lib_enum_mixin.py

**enum-comparison-dispatch.** str/Enum and int/Enum mixin comparisons use immutable payloads, including accepting scalar fallback. StrEnum construction and mutable value/hash/string operations reflect the added hidden slot. N integer object eq/order helpers use immutable integers. Mappingproxy/iterator/members-view helpers are identical after exact literal/metadata resolution. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline differs from the prior baseline, so its additional pre-repair delta was separately retained and reviewed. Earlier alpha.2-to-pre-repair changes remove one uncalled mappingproxy.__ror__ specialization and now-unused dict-copy/update declarations; no retained call references that method.

### 1621: tests/programs/library/lib_enum_plain_isinstance.py

**enum-comparison-dispatch.** Although source only defines plain Color(Enum), the Any descriptor for an Enum-typed value requests helpers across the imported Enum hierarchy. The eq/ne/cmp helpers for Enum, ReprEnum, IntEnum, StrEnum, _IntMixin, _StrMixin, Flag and IntFlag inline scalar comparisons only for numeric/string enum arms. Identity/null/error arms remain; every ordering error-arm sequence is byte-identical after resolving literal IDs. IntEnum/StrEnum base helpers split the prior shared subclass row into explicit concrete slot-load pairs; no new type alternatives are admitted. The dynamic o.x cross-type methods and their 35 renamed inherited method/_int_of/_str_of specializations retain identical bodies/call graphs after matching names and the expected StrEnum mutable-field shift. dyn.get._value_ continues to read mutable _value_ with its assigned-bit guard, with only StrEnum/_StrMixin indices3/4 becoming4/5. Main and is_integer bodies are byte-identical. Metadata differences are the new StrEnum slot/layout and newly referenced immutable integer slots; strings are renumbered as unused static comparison helpers disappear. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1622: tests/programs/library/lib_enum_reflected.py

**enum-comparison-dispatch.** Existing reflected-comparison program: only main changes, with immutable numeric/string enum payload stages replacing inherited comparisons. Custom Other comparison methods and Plain/Color helpers remain byte-identical. Hidden Word string slot is initialized and used for scalar fallback; dead inherited scalar helpers disappear. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1624: tests/programs/library/lib_enum_values.py

**enum-field-layout.** StrEnum T gains the immutable string slot; its three constructors initialize that slot, and the value/assigned fields shift 3/4 to 4/5 with corresponding TBAA offsets. All 50 function bodies are otherwise identical after exact expected layout changes and bijective SSA/metadata resolution. Other enum literal/value handling is unchanged. Evidence: layout-only-review-evidence.json. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1625: tests/programs/library/lib_flag_base_lookup.py

**enum-comparison-dispatch.** Base Flag lookup includes a possible IntFlag value alternative. That alternative alone replaces inherited IntFlag.__eq__ with a slot5 immutable integer load and icmp. Plain Flag contains/repr/value-repr helpers are identical after exact literal/metadata resolution. This case is independently tied to the retained prior repair review by whole candidate IR equality after only validated checkout-home literals. The broad baseline also has whole IR equality to the prior baseline; therefore its entire delta is identical.

### 1626: tests/programs/library/lib_fnmatch.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1627: tests/programs/library/lib_fnmatch_raw_bytes.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1628: tests/programs/library/lib_fnmatch_unicode_ranges.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1635: tests/programs/library/lib_functools_reduce.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1638: tests/programs/library/lib_gettext.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1639: tests/programs/library/lib_glob.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1642: tests/programs/library/lib_html.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1643: tests/programs/library/lib_html_entities.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1644: tests/programs/library/lib_html_parser.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1645: tests/programs/library/lib_html_parser_positions.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1646: tests/programs/library/lib_io.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1647: tests/programs/library/lib_io_bytesio.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1648: tests/programs/library/lib_io_cmodule.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. The fixed IO class methods and all callers are exactly identical after the explicit class/type/function-name map. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 1649: tests/programs/library/lib_io_codepoints.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1650: tests/programs/library/lib_io_newline_decoder.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. IncrementalNewlineDecoder allocation moves immediately before the same global decoder-argument load. Initialization and subsequent decoder operations are unchanged. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 1651: tests/programs/library/lib_io_textiowrapper.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1652: tests/programs/library/lib_io_textiowrapper_bytesio.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1653: tests/programs/library/lib_io_textiowrapper_newlines_none.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1654: tests/programs/library/lib_io_textiowrapper_unreadable.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1655: tests/programs/library/lib_io_type_module.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. The type-module IO class methods and all callers are exactly identical after the explicit class/type/function-name map. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 1658: tests/programs/library/lib_itertools_gc.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1659: tests/programs/library/lib_itertools_generators.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1663: tests/programs/library/lib_itertools_module.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1664: tests/programs/library/lib_itertools_range.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1666: tests/programs/library/lib_itertools_terminating.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1670: tests/programs/library/lib_logging.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only itertools._count and threading._counter change: count yields integer identity and _counter returns it through the existing identity output.

### 1671: tests/programs/library/lib_logging_config.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only the imported itertools._count and threading._counter identity channels change; logging configuration and handler behavior remain.

### 1672: tests/programs/library/lib_logging_int_min.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only the imported itertools._count and threading._counter identity channels change; minimum-int logging formatting remains.

### 1673: tests/programs/library/lib_logging_make_record.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only the imported itertools._count and threading._counter identity channels change; LogRecord construction remains.

### 1674: tests/programs/library/lib_logging_stderr.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only the imported itertools._count and threading._counter identity channels change; stderr logging behavior remains.

### 1678: tests/programs/library/lib_pathlib.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1679: tests/programs/library/lib_pathlib_glob_case.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1681: tests/programs/library/lib_random.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1682: tests/programs/library/lib_random_distributions.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1683: tests/programs/library/lib_random_sequences.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1684: tests/programs/library/lib_random_triangular_ints.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1685: tests/programs/library/lib_re.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1686: tests/programs/library/lib_re_annotations.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1687: tests/programs/library/lib_re_bounds.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1688: tests/programs/library/lib_re_branch_filter.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1689: tests/programs/library/lib_re_branch_runs.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1690: tests/programs/library/lib_re_cache.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1691: tests/programs/library/lib_re_cache_churn.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1692: tests/programs/library/lib_re_charset.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1693: tests/programs/library/lib_re_class_span.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1694: tests/programs/library/lib_re_codepoints.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1695: tests/programs/library/lib_re_first.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1696: tests/programs/library/lib_re_flat.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1697: tests/programs/library/lib_re_groups.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1698: tests/programs/library/lib_re_ignorecase_repeat.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1699: tests/programs/library/lib_re_inline_flags.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1700: tests/programs/library/lib_re_lines.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1701: tests/programs/library/lib_re_prefilter.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1702: tests/programs/library/lib_re_purge.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1703: tests/programs/library/lib_re_raw_subject.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1704: tests/programs/library/lib_re_repeat_prefix.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1705: tests/programs/library/lib_re_reuse.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1706: tests/programs/library/lib_re_unicode_memo.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1707: tests/programs/library/lib_re_utf8_overlong.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1711: tests/programs/library/lib_shlex.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1712: tests/programs/library/lib_shlex_upstream.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1723: tests/programs/library/lib_string.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1724: tests/programs/library/lib_string_formatter.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1725: tests/programs/library/lib_string_formatter_mixed.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1726: tests/programs/library/lib_string_formatter_subclass.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1727: tests/programs/library/lib_string_template_kwargs.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1728: tests/programs/library/lib_struct.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1729: tests/programs/library/lib_textwrap.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1730: tests/programs/library/lib_textwrap_codepoints.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1731: tests/programs/library/lib_textwrap_whitespace.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1734: tests/programs/library/lib_threading.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Alongside _count/_counter identity channels, Barrier._enter/_exit add identity-first membership for state integers -1 and 1 before the same equality checks. Barrier synchronization and state transitions are otherwise unchanged.

### 1736: tests/programs/library/lib_tomllib.py

**toml-tuple-null-guards-and-layout.** Runtime tuple allocation/iteration follows the added identity header. The key-value, dict-rule and list-rule paths check a nullable tuple pointer before loading its length; the null branch raises the existing TypeError instead of dereferencing None. datetime fold membership gains identity-before-equality. The unreferenced mappingproxy.__ror__ method and now-unused declarations disappear. Every changed retained function has the exact same old/new canonical body as the corresponding independently inspected function in case 1736; the equality check retains exact literal and metadata contents. The removed reflected symbol has no remaining references.

### 1737: tests/programs/library/lib_tomllib_boundary.py

**toml-tuple-null-guards-and-layout.** Runtime tuple allocation/iteration follows the added identity header. The key-value, dict-rule and list-rule paths check a nullable tuple pointer before loading its length; the null branch raises the existing TypeError instead of dereferencing None. datetime fold membership gains identity-before-equality. The unreferenced mappingproxy.__ror__ method and now-unused declarations disappear. Every changed retained function has the exact same old/new canonical body as the corresponding independently inspected function in case 1736; the equality check retains exact literal and metadata contents. The removed reflected symbol has no remaining references.

### 1738: tests/programs/library/lib_tomllib_dynamic.py

**toml-tuple-null-guards-and-layout.** Runtime tuple allocation/iteration follows the added identity header. The key-value, dict-rule and list-rule paths check a nullable tuple pointer before loading its length; the null branch raises the existing TypeError instead of dereferencing None. datetime fold membership gains identity-before-equality. The unreferenced mappingproxy.__ror__ method and now-unused declarations disappear. Every changed retained function has the exact same old/new canonical body as the corresponding independently inspected function in case 1736; the equality check retains exact literal and metadata contents. The removed reflected symbol has no remaining references.

### 1739: tests/programs/library/lib_tomllib_flags.py

**toml-tuple-null-guards-and-layout.** Runtime tuple allocation/iteration follows the added identity header. The key-value, dict-rule and list-rule paths check a nullable tuple pointer before loading its length; the null branch raises the existing TypeError instead of dereferencing None. datetime fold membership gains identity-before-equality. The unreferenced mappingproxy.__ror__ method and now-unused declarations disappear. Every changed retained function has the exact same old/new canonical body as the corresponding independently inspected function in case 1736; the equality check retains exact literal and metadata contents. The removed reflected symbol has no remaining references.

### 1740: tests/programs/library/lib_tomllib_typed_callback.py

**toml-tuple-null-guards-and-layout.** Only datetime fold membership gains identity-before-equality, and the unreferenced mappingproxy.__ror__ method disappears. Every changed retained function has the exact same old/new canonical body as the corresponding independently inspected function in case 1736; the equality check retains exact literal and metadata contents. The removed reflected symbol has no remaining references.

### 1741: tests/programs/library/lib_tomllib_uncaught.py

**toml-tuple-null-guards-and-layout.** Runtime tuple allocation/iteration follows the added identity header. The key-value, dict-rule and list-rule paths check a nullable tuple pointer before loading its length; the null branch raises the existing TypeError instead of dereferencing None. datetime fold membership gains identity-before-equality. The unreferenced mappingproxy.__ror__ method and now-unused declarations disappear. Every changed retained function has the exact same old/new canonical body as the corresponding independently inspected function in case 1736; the equality check retains exact literal and metadata contents. The removed reflected symbol has no remaining references.

### 1742: tests/programs/library/lib_traceback.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1743: tests/programs/library/lib_types_mappingproxy.py

**unreferenced-reflected-specialization-removal.** Only unused mappingproxy.__ror__ specializations disappear, together with now-unused runtime declarations where applicable. Every removed symbol has zero references outside the removed definitions in the old module. All retained function bodies match after exact literal/metadata resolution. This follows lazy admission of reflected methods and removes no executed call.

### 1744: tests/programs/library/lib_types_mappingproxy_opaque.py

**unreferenced-reflected-specialization-removal.** Only unused mappingproxy.__ror__ specializations disappear, together with now-unused runtime declarations where applicable. Every removed symbol has zero references outside the removed definitions in the old module. All retained function bodies match after exact literal/metadata resolution. This follows lazy admission of reflected methods and removes no executed call.

### 1746: tests/programs/library/lib_unicodedata_chars.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1748: tests/programs/library/lib_urllib_parse.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1749: tests/programs/library/lib_urllib_parse_cache.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1750: tests/programs/library/lib_warnings.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1751: tests/programs/library/lib_warnings_main_filter.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1752: tests/programs/library/lib_warnings_objects.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1753: tests/programs/library/lib_warnings_options.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1754: tests/programs/library/lib_warnings_skip_prefixes.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1755: tests/programs/library/lib_weakref.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1756: tests/programs/library/lib_weakref_callback.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1757: tests/programs/library/lib_weakref_callback_dead_ref.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1758: tests/programs/library/lib_weakref_callback_nested.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1759: tests/programs/library/lib_weakref_callback_order.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1760: tests/programs/library/lib_weakref_callback_raise.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1761: tests/programs/library/lib_weakref_dead.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1762: tests/programs/library/lib_weakref_dead_eq.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1763: tests/programs/library/lib_weakref_eq.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 1764: tests/programs/library/lib_weakref_module.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1765: tests/programs/library/lib_weakref_star.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1766: tests/programs/library/lib_weakref_transition.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1778: tests/programs/library/re_specialize.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1779: tests/programs/library/re_specialize_recursion.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1781: tests/programs/library/sys_prefix.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1875: tests/programs/numbers/mpz_cpython_long_bitops.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1876: tests/programs/numbers/mpz_cpython_long_division.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1877: tests/programs/numbers/mpz_cpython_text.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 1896: tests/programs/numbers/python_int_any_containers.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1944: tests/programs/numbers/python_int_generator_identity.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Promoting-int generator frames grow from 9 to 10 words, preserving raw low/high fields and appending identity at slot 9. Integer consumers reuse a matching int box or bigint box only after checking its type and exact wide-pointer payload; otherwise they create a box. Fresh yields store null, aliases preserve boxes, and float yields in the same promoting program use that same companion slot. Yield-from and main assignments snapshot identities before resume and preserve wide/narrow checks.

### 1965: tests/programs/numbers/python_int_optional_container_identity.py

**numeric-container-identity-companions.** Optional promoting-int list/VTuple operations preserve kinds 9 companions for small, minimum-width and shared items. Removing a temporary fixed tuple preserves its original coerced payloads and wide checks before final VTuple storage. Pop carries the saved identity while reconstructing the optional representation. Raw-int tuples use kind 1 and widening to optional storage keeps those same identities. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1968: tests/programs/numbers/python_int_optional_tuple_identity.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1978: tests/programs/numbers/python_int_storage.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1986: tests/programs/numbers/python_int_tuple_walks.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 1992: tests/programs/numbers/python_int_vtuple_identity.py

**numeric-container-identity-companions.** Promoting-int VTuple item reads use the retained companion and exact unboxing, including the imported checked.first path; construction and copy paths reserve and preserve the identity header. Wide/narrow numeric payload checks are retained. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 1994: tests/programs/numbers/python_int_vtuple_materialization.py

**numeric-container-identity-companions.** Dynamic conversion adds only the VTuple header. Optional materialization eliminates an intermediate fixed-tuple allocation while retaining original element evaluations/coercions and saving their identities before final storage. Small/promoting items reuse a bigint companion only when its type and high-pointer payload match; otherwise they call pys_dyn_big. Checked narrowing still rejects a value that does not fit. The per-function and globals inventories retain every other change for this case; this is an intended identity-semantics repair, not a claim of raw IR equivalence.

### 2010: tests/programs/optimizations/opt_alloc_held_cohort.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2011: tests/programs/optimizations/opt_alloc_held_fields.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2012: tests/programs/optimizations/opt_alloc_held_tuple.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2195: tests/programs/reflection/reflect_formatter.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2214: tests/programs/reflection/type_alias_annotations.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2217: tests/programs/reflection/type_alias_imports.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2220: tests/programs/reflection/types_generic_alias.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2221: tests/programs/reflection/types_generic_alias_constants.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2222: tests/programs/reflection/types_generic_alias_subscripts.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2369: tests/programs/strings/str_join_slice_bounds.py

**unused-numeric-identity-capture-and-constants.** String-join slice-bound lowering adds only explicitly recorded unused numeric identity calls. The two added static identity objects for -2**63 and -100 each have exactly one module reference, their own definition. All remaining function instructions and global payloads match; bounds and error handling do not change.

### 2389: tests/programs/strings/unicode_library_codepoints.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2408: tests/programs/upstream/upstream_argparse_options.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2414: tests/programs/upstream/upstream_builtin_min_max_sum.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2416: tests/programs/upstream/upstream_builtin_zip_sorted.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2419: tests/programs/upstream/upstream_call_kwargs.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. C allocation moves before the same kwargs-record materialization; keyword order, values, stores and initializer invocation are preserved. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 2422: tests/programs/upstream/upstream_contextlib_locks.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only the imported itertools._count/threading._counter identity channels change; context-manager and lock behavior remain.

### 2423: tests/programs/upstream/upstream_copy_extracted.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2424: tests/programs/upstream/upstream_copy_extracted_any.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2428: tests/programs/upstream/upstream_counter.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2436: tests/programs/upstream/upstream_dict_methods.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2438: tests/programs/upstream/upstream_dictcomps.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2440: tests/programs/upstream/upstream_difflib_context.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2446: tests/programs/upstream/upstream_float_format.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2450: tests/programs/upstream/upstream_fnmatch.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2453: tests/programs/upstream/upstream_functools_cache.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2456: tests/programs/upstream/upstream_glob_escape.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2457: tests/programs/upstream/upstream_heapq_extracted.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2458: tests/programs/upstream/upstream_html_parser.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2460: tests/programs/upstream/upstream_int_arith.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2462: tests/programs/upstream/upstream_int_format.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2468: tests/programs/upstream/upstream_itertools.py

**fixed-constructor-and-runtime-tuple-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. The S iterator class and its callers retain exact bodies after the S-1 -> S mapping except for 18 named functions. Fourteen have only precisely verified VTuple header/allocation/iteration changes. TestVariousIteratorArgs_tests additionally has the same tuple changes and S allocation before the same argument load. various.1, various.2 and various_numbers move only zeroed S allocation before argument loads or literal [1,2,3,4,5] construction; argument values and initializer-before-iterator-use order are preserved. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 2472: tests/programs/upstream/upstream_listcomps.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2479: tests/programs/upstream/upstream_math_sums.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2520: tests/programs/upstream/upstream_ordered_dict.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2521: tests/programs/upstream/upstream_positional_only_arg_extracted.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2526: tests/programs/upstream/upstream_random.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2528: tests/programs/upstream/upstream_re_errors.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2529: tests/programs/upstream/upstream_re_flags.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2530: tests/programs/upstream/upstream_re_match.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2531: tests/programs/upstream/upstream_re_sub.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2532: tests/programs/upstream/upstream_re_tests.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2533: tests/programs/upstream/upstream_re_tests_perl.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2543: tests/programs/upstream/upstream_shlex_punctuation.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 2545: tests/programs/upstream/upstream_slice_steps.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2546: tests/programs/upstream/upstream_sort_extracted.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2549: tests/programs/upstream/upstream_string_formatter.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2552: tests/programs/upstream/upstream_textwrap_field_rebind.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2553: tests/programs/upstream/upstream_textwrap_indent.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2554: tests/programs/upstream/upstream_textwrap_layout.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2555: tests/programs/upstream/upstream_textwrap_unicode.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2556: tests/programs/upstream/upstream_textwrap_wrap.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2557: tests/programs/upstream/upstream_tomllib_data.py

**toml-tuple-null-guards-and-layout.** Runtime tuple allocation/iteration follows the added identity header. The key-value, dict-rule and list-rule paths check a nullable tuple pointer before loading its length; the null branch raises the existing TypeError instead of dereferencing None. datetime fold membership gains identity-before-equality. The unreferenced mappingproxy.__ror__ method and now-unused declarations disappear. Every changed retained function has the exact same old/new canonical body as the corresponding independently inspected function in case 1736; the equality check retains exact literal and metadata contents. The removed reflected symbol has no remaining references.

### 2558: tests/programs/upstream/upstream_tomllib_misc.py

**toml-tuple-null-guards-and-layout.** Runtime tuple allocation/iteration follows the added identity header. The key-value, dict-rule and list-rule paths check a nullable tuple pointer before loading its length; the null branch raises the existing TypeError instead of dereferencing None. datetime fold membership gains identity-before-equality. The unreferenced mappingproxy.__ror__ method and now-unused declarations disappear. Every changed retained function has the exact same old/new canonical body as the corresponding independently inspected function in case 1736; the equality check retains exact literal and metadata contents. The removed reflected symbol has no remaining references.

### 2565: tests/programs/upstream/upstream_weakref.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2588: tests/deviations/dynany_class_construct_deferred.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2602: tests/deviations/dynany_generator_channel_check.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. The documented dynamic-to-typed generator-channel deviation remains: existing checked conversion and exceptional ownership/cleanup paths are retained. The changed IR adds only the yielded companion and snapshots; it does not establish new support for the documented deviation.

### 2603: tests/deviations/dynany_generator_channel_check_protocol.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. The documented protocol-channel deviation and its conversion error remain. The concrete numeric channel adds the companion without changing send/close behavior.

### 2607: tests/deviations/dynany_native_int_list_store.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2636: tests/deviations/lib_copy_any_object.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2638: tests/deviations/lib_datetime.py

**datetime-comment-only-source-and-path.** Whole IR is identical after the validated checkout-home literal replacement. datetime.py bytes do differ, so this is deliberately not classified as unchanged-library path-only: its full parsed AST is identical and the retained source diff contains only the reflected-timedelta comments. No instruction or diagnostic change remains.

### 2639: tests/deviations/lib_fnmatch_byte_boundaries.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2641: tests/deviations/lib_html_parser_names.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2642: tests/deviations/lib_io_newline_decoder_object.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. The zeroed newline-decoder allocation moves before constructing its Latin1 argument; Latin1 initialization still completes before decoder initialization. No user-defined allocation hook or initializer is reordered. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 2643: tests/deviations/lib_io_newline_decoder_tuple.py

**fixed-constructor-admission-and-layout.** The admitted fixed layout uses the explicit class/type/TBAA/function mappings in constructor-equivalence.json; this is not a general type-name normalization. The tuple decoder methods and all callers are exactly identical after the explicit class/type/function-name map. Every other function is exactly equal after that case-specific map. Moving the built-in zeroed allocation changes storage preparation, not the order of user initializer or argument effects.

### 2644: tests/deviations/lib_io_textiowrapper.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 2649: tests/deviations/lib_itertools_hasattr.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2650: tests/deviations/lib_itertools_protocol.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2653: tests/deviations/lib_logging_exc_info.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only the imported counter identity channels change; the existing logging exc_info deviation remains.

### 2654: tests/deviations/lib_markupbase_constructor.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2655: tests/deviations/lib_module_doc.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 2656: tests/deviations/lib_pathlib_unsupported.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2657: tests/deviations/lib_random.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2658: tests/deviations/lib_re.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2659: tests/deviations/lib_re_bounded_decoding.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2660: tests/deviations/lib_re_cache_policy.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2661: tests/deviations/lib_re_decoding.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2662: tests/deviations/lib_re_purge_decoding.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2663: tests/deviations/lib_re_release.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2664: tests/deviations/lib_shlex.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 2667: tests/deviations/lib_string.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2668: tests/deviations/lib_string_formatter_fields.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2674: tests/deviations/lib_types_mappingproxy_eq_other.py

**unreferenced-reflected-specialization-removal.** Only unused mappingproxy.__ror__ specializations disappear, together with now-unused runtime declarations where applicable. Every removed symbol has zero references outside the removed definitions in the old module. All retained function bodies match after exact literal/metadata resolution. This follows lazy admission of reflected methods and removes no executed call.

### 2675: tests/deviations/lib_urllib_parse.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2676: tests/deviations/lib_warnings_location.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2677: tests/deviations/lib_warnings_message_type.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2678: tests/deviations/lib_weakref_all.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2686: tests/deviations/python_int_limits.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2699: tests/deviations/threading_start.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only the imported counter identity channels change; the existing threading.start deviation remains.

### 2700: tests/deviations/tuple_runtime_identity.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

### 2706: bench/itertools_loops.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2719: bench/pyperformance/bm_logging.py

**numeric-generator-identity-channel.** The numeric coroutine promise appends a nullable object-identity word after its existing raw/protocol/wide fields. Producers preserve alias boxes or use null for fresh computed values, and consumers copy the companion into a private slot before the next resume; raw numeric value layout and cleanup remain. Only the logging benchmark imported counter identity channels change; benchmark work and logging calls are unchanged.

### 2720: bench/pyperformance/bpe_tokeniser.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2722: bench/pyperformance/comprehensions.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 2727: bench/pyperformance/hexiom.py

**unused-class-type-declarations-only.** After verified path literals, differences are only listed class type declarations, none referenced anywhere outside the declaration block. All instructions, constants, metadata and function bodies are byte-identical.

### 2729: bench/pyperformance/json_loads.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2730: bench/pyperformance/meteor_contest.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2735: bench/pyperformance/regex_dna.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2736: bench/pyperformance/regex_effbot.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2737: bench/pyperformance/regex_v8.py

**verified-checkout-path-literals-only.** Whole IR identical after exact compiler-home replacements confined to validated LLVM string constants; string header lengths and referenced library input bytes verified. No instruction, diagnostic, or type change.

### 2795: tests/ir/tuple_const.py

**runtime-tuple-header-layout.** The runtime-length tuple now reserves one scanned identity-pointer word after its length. Each recorded allocation grows from 8*(len+1) to 8*(len+2), matching stored length; item addresses and direct tuple iteration move by exactly one word. The addressed objects in the named iteration functions are VTuples. The exact per-function check accounts for every changed instruction: element values, indices, iteration bounds, ordering and control flow are otherwise unchanged. This does not reinterpret fixed tuples or their constant data.

