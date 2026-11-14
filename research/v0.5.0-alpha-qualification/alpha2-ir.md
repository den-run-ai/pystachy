# Alpha.2 exact-source IR audit

Final alpha.1 `41cc2dde4705efcf03d9d910455ac72fd5da2312` → published alpha.2 candidate `591cd8bdab6fdb54aa036d5094079a32af4fac25`.

**4,579 cases complete; 0 new rejections; all 33 substantive differences explained.** Raw oracle exit 1 records 309 differences: 4,270 raw-identical cases, 262 generated-home-only LLVM differences, 14 source-location-only diagnostics, 17 intended new acceptances, 10 shared-dispatch LLVM changes and 6 more precise diagnostics on already-rejected programs. Compiler-self and runtime IR are raw-identical between the compilers.

The candidate binary came from the completed local `9997bf2c1551f177506c2c3b2d095c940df715d9` bootstrap; its tree equals public candidate tree `9493b8219a543ddbc1d8c17e5c24b026e2c82d38`. All three compiler stages and all three runtime stages were byte-identical, and the audit binary matched stage 2. Final alpha.1 uses the already qualified snapshot. Identity files record public/local source equivalence, all compiler/runtime hashes, full source inventory, corpus identities and unchanged post-run inputs.

Both compilers use separate exact-source libraries in equal-length `home-a1`/`home-a2` directories. The oracle retains complete exit statuses, diagnostics and every changed raw LLVM/diff. The complete canonical corpus plus compiler/runtime, benchmark and IR cases is verified in inventory order.

Only recognized generated home strings and reviewed diagnostic source locations receive auxiliary location comparison. Twenty shared-corpus import strings are byte-identical on both sides and remain unchanged, as recorded separately. No broader normalization is used.

The 33-case substantive set exactly matches the prior independently explained audit. All fixture sources and all diagnostics are unchanged. Twenty-five complete old/new LLVM pairs are byte-identical to prior evidence; the remaining eight pairs differ only in the individually verified MappingProxyType ImportError source-home constant and its corresponding string-size fields. Thus the original shared-dispatch control-flow explanations still describe these exact final outputs. Full evidence is in `a2-historical-ir-recheck.json`.

This comparison does not measure AOT runtime-cache performance or replace native execution, Lean proof coverage or exact-main release CI. Those are separate qualification evidence.

| Case | Category | Explanation |
|---|---|---|
| `tests/programs/classes/class_attr_default.py` | new_acceptance | A class-body method default may read an earlier single-assignment class attribute. |
| `tests/programs/classes/class_body_consts.py` | new_acceptance | Non-scalar Final values and subsequent class-body constants/defaults are inferred in order. |
| `tests/programs/classes/class_consts_raise.py` | new_acceptance | A later class constant may read an earlier class constant, retaining its runtime evaluation/error order. |
| `tests/programs/classes/classvar_attrs.py` | new_acceptance | Initialized ClassVar attributes are accepted, including the imported support module. |
| `tests/programs/classes/final_class_values.py` | new_acceptance | Ordinary class-body non-scalar Final values are accepted with inferred types. |
| `tests/programs/classes/generic_visitor.py` | new_acceptance | Concrete generic visitor bases without constructor-binding type variables are accepted. |
| `tests/programs/classes/generic_visitor_class_fields.py` | new_acceptance | Combined generic visitor, constructed template fields and class constant/default behavior is accepted. |
| `tests/programs/classes/generic_visitor_inherited_classmethod.py` | new_acceptance | Inherited classmethods on concrete generic visitor bases are accepted. |
| `tests/programs/classes/generic_visitor_inherited_classmethod_field.py` | new_acceptance | Inherited generic visitor classmethods work with annotated instance fields. |
| `tests/programs/classes/generic_visitor_postponed.py` | new_acceptance | Generic visitor calls with postponed/recursive method relationships are accepted. |
| `tests/programs/classes/generic_visitor_static_methods.py` | new_acceptance | Supported static methods coexist with concrete generic visitor bases. |
| `tests/programs/classes/inheritance_dispatch_wide.py` | ir_change | Extracts 11 shared dispatchers at 19 call sites, with distinct method/argument signatures and override defaults preserved. Null checks, argument evaluation and exception propagation remain; small hierarchies remain inline. |
| `tests/programs/classes/inheritance_template_fields.py` | new_acceptance | A constructed template in an annotated instance field no longer wrongly classifies the outer class as a template, enabling inheritance. |
| `tests/programs/classes/inheritance_template_param.py` | new_acceptance | That classification follows typed constructor-parameter dependencies, preserving ordinary-class inheritance. |
| `tests/programs/exceptions/exc_class_exit_enum.py` | ir_change | Extracts the 10-arm non-dunder _value_repr_ dispatch from Enum.__repr__.2 into @vd.0. Ordered method targets, tag predicates and final default arm match the old inline dispatch; helper checks null before tag and counts no recursion frame. SystemExit conversion is unchanged. |
| `tests/programs/exceptions/exc_exit_enum_stored.py` | ir_change | Extracts the 10-arm non-dunder _value_repr_ dispatch from Enum.__repr__.1 into @vd.0. Ordered method targets, tag predicates and final default arm match the old inline dispatch; helper checks null before tag and counts no recursion frame. SystemExit conversion is unchanged. |
| `tests/programs/exceptions/exit_enum_member_caught.py` | ir_change | Extracts the 12-arm non-dunder _value_repr_ dispatch from Enum.__repr__.4 into @vd.0. Ordered method targets, tag predicates and final default arm match the old inline dispatch; helper checks null before tag and counts no recursion frame. SystemExit conversion is unchanged. |
| `tests/programs/exceptions/exit_enum_member_message.py` | ir_change | Extracts the 10-arm non-dunder _value_repr_ dispatch from Enum.__repr__.1 into @vd.0. Ordered method targets, tag predicates and final default arm match the old inline dispatch; helper checks null before tag and counts no recursion frame. SystemExit conversion is unchanged. |
| `tests/programs/exceptions/exit_enum_nonint_protocol.py` | ir_change | Extracts the 10-arm non-dunder _value_repr_ dispatch from Enum.__repr__.1 into @vd.0. Ordered method targets, tag predicates and final default arm match the old inline dispatch; helper checks null before tag and counts no recursion frame. SystemExit conversion is unchanged. |
| `tests/programs/exceptions/exit_enum_stored_status.py` | ir_change | Extracts the 9-arm non-dunder _value_repr_ dispatch from Enum.__repr__.1 into @vd.0. Ordered method targets, tag predicates and final default arm match the old inline dispatch; helper checks null before tag and counts no recursion frame. SystemExit conversion is unchanged. |
| `tests/programs/exceptions/exit_intflag_stored_mutated.py` | ir_change | Extracts the 9-arm non-dunder _value_repr_ dispatch from Enum.__repr__.1 into @vd.0. Ordered method targets, tag predicates and final default arm match the old inline dispatch; helper checks null before tag and counts no recursion frame. SystemExit conversion is unchanged. |
| `tests/programs/imports/import_class_attr_default.py` | new_acceptance | Imported class attribute is usable in a later class-body method default. |
| `tests/programs/imports/import_class_builtin_default.py` | new_acceptance | Earlier class attribute shadowing a builtin is usable in its method default. |
| `tests/programs/imports/import_class_name_default.py` | new_acceptance | Earlier class __name__ attribute is usable in its method default. |
| `tests/programs/language/recursion_virtual_frames.py` | ir_change | Extracts one 11-arm down dispatcher used at 15 sites. Concrete recursive methods use ordinary recursion-enter/restore paths; the helper adds no counted recursion frame. |
| `tests/programs/library/lib_enum_base_lookup.py` | ir_change | Extracts the 12-arm non-dunder _value_repr_ dispatch from Enum.__repr__.1 into @vd.0. Ordered method targets, tag predicates and final default arm match the old inline dispatch; helper checks null before tag and counts no recursion frame. SystemExit conversion is unchanged. |
| `tests/programs/library/typing_classvar.py` | new_acceptance | Initialized typing.ClassVar declaration is now accepted. |
| `tests/errors/classes/final_class_value_uninferred.py` | diagnostic_change | Still rejected: Final value has no inferable element type. Diagnostic now asks specifically for KEYS: Final[T] instead of rejecting all non-scalar untyped Final values. |
| `tests/errors/classes/generic_base_arity.py` | diagnostic_change | Still rejected: generic base has two arguments for one type parameter; now reports its exact arity. |
| `tests/errors/classes/generic_base_init.py` | diagnostic_change | Still rejected: the generic base constructor binds its own type variables. The message now names this unsupported inheritance boundary. |
| `tests/errors/classes/generic_base_typevar.py` | diagnostic_change | Still rejected: pass-through subclass TypeVar has no supported binding context. More precise TypeVar-context error replaces general unsupported-base error. |
| `tests/errors/classes/generic_visitor_base_variable.py` | diagnostic_change | Still rejected: generic visitor overrides return incompatible types through a base-typed variable. Newly recognized base reaches the concrete return-type conflict. |
| `tests/errors/classes/inheritance_template_param_field.py` | diagnostic_change | Still rejected: an unannotated pending field has no inferred type. Removing false outer-template classification exposes the actual missing annotation. |
