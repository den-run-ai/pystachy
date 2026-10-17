"""Gen component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import os
from src.pystachy_compiler.lowering import gen_lower_scalar as scalar_ir_lower_scalar
from src.pystachy_compiler.scalar_ir import (
    gen_scalar as scalar_ir_scalar,
    gen_scalar_cast as scalar_ir_scalar_cast,
    gen_scalar_cmp as scalar_ir_scalar_cmp,

    gen_verify_scalar as scalar_ir_verify_scalar,
)
from src.pystachy_compiler.union_arithmetic import (
    gen_unumeric as union_arithmetic_unumeric,
    gen_unumeric_case as union_arithmetic_unumeric_case,
)
from src.pystachy_compiler.memory_ir import (
    gen_mload as memory_ir_mload,
    gen_mstore as memory_ir_mstore,
    gen_maddr as memory_ir_maddr,
)
from src.pystachy_compiler.unions import (
    gen_ueq_type as unions_ueq_type,
    gen_scalar_union as unions_scalar_union,
    gen_value_union as unions_value_union,
    gen_uop as unions_uop,
    gen_uequal as unions_uequal,
    gen_reference_union as unions_reference_union,
    gen_umethod as unions_umethod,
    gen_uboxes as unions_uboxes,
    gen_umember_problem as unions_umember_problem,
    gen_union_type as unions_union_type,
    gen_utag as unions_utag,
    gen_ubox as unions_ubox,
    gen_uget as unions_uget,
    gen_utest as unions_utest,
    gen_to_union as unions_to_union,
    gen_narrow_val as unions_narrow_val,
    gen_unarrowed as unions_unarrowed,
    gen_uisinst as unions_uisinst,
    gen_now_type as unions_now_type,
    gen_isinst_narrow as unions_isinst_narrow,
    gen_holds as unions_holds,
)
from src.pystachy_compiler.reflection import (
    RArm,
    RLeaf,
    RText,
    gen_refl_typeof as reflection_refl_typeof,
    gen_refl_concrete as reflection_refl_concrete,
    gen_refl_may_none as reflection_refl_may_none,
    gen_refl_split as reflection_refl_split,
    gen_refl_split_class as reflection_refl_split_class,
    gen_refl_type_name as reflection_refl_type_name,
    gen_refl_record as reflection_refl_record,
    gen_refl_type_of as reflection_refl_type_of,
    gen_refl_class_of as reflection_refl_class_of,
    gen_refl_type_attr as reflection_refl_type_attr,
    gen_refl_type_operand as reflection_refl_type_operand,
    gen_refl_type_cmp as reflection_refl_type_cmp,
    gen_refl_derived_only as reflection_refl_derived_only,
    gen_refl_replace_changes as reflection_refl_replace_changes,
    gen_refl_hasattr_lit as reflection_refl_hasattr_lit,
    gen_refl_prop_in as reflection_refl_prop_in,
    gen_refl_name_list as reflection_refl_name_list,
    gen_refl_names_table as reflection_refl_names_table,
    gen_refl_runtime_name as reflection_refl_runtime_name,
    gen_refl_find as reflection_refl_find,
    gen_refl_hasattr as reflection_refl_hasattr,
    gen_refl_otext as reflection_refl_otext,
    gen_refl_lookup as reflection_refl_lookup,
    gen_refl_lookup_text as reflection_refl_lookup_text,
    gen_refl_arm_text as reflection_refl_arm_text,
    gen_refl_setattr_runtime as reflection_refl_setattr_runtime,
    gen_refl_union_str as reflection_refl_union_str,
    gen_refl_dc_class as reflection_refl_dc_class,
    gen_refl_dc_check as reflection_refl_dc_check,
    gen_refl_dc_names as reflection_refl_dc_names,
    gen_refl_unroll_fields as reflection_refl_unroll_fields,
    gen_refl_dc_type as reflection_refl_dc_type,
    gen_refl_dc_copy as reflection_refl_dc_copy,
    gen_refl_dataclasses as reflection_refl_dataclasses,
    gen_refl_dir_names as reflection_refl_dir_names,
    gen_refl_dir as reflection_refl_dir,
    gen_refl_dir_of as reflection_refl_dir_of,
    gen_refl_dict_copy as reflection_refl_dict_copy,
    gen_refl_dict_format as reflection_refl_dict_format,
    gen_refl_percent as reflection_refl_percent,
    gen_refl_format_map as reflection_refl_format_map,
    gen_refl_unroll_dict as reflection_refl_unroll_dict,
    gen_refl_size_check as reflection_refl_size_check,
    gen_refl_dict_operand as reflection_refl_dict_operand,
    gen_refl_supported as reflection_refl_supported,
    gen_refl_defines as reflection_refl_defines,
    gen_refl_names as reflection_refl_names,
    gen_refl_listed as reflection_refl_listed,
    gen_refl_public as reflection_refl_public,
    gen_refl_init_order as reflection_refl_init_order,
    gen_refl_dict_order as reflection_refl_dict_order,
    gen_refl_stored as reflection_refl_stored,
    gen_refl_late as reflection_refl_late,
    gen_refl_fields_table as reflection_refl_fields_table,
    gen_refl_layout_record as reflection_refl_layout_record,
    gen_refl_dict_of as reflection_refl_dict_of,
    gen_refl_vars_text as reflection_refl_vars_text,
    gen_refl_textual as reflection_refl_textual,
    gen_refl_defer as reflection_refl_defer,
    gen_refl_finish as reflection_refl_finish,
    gen_refl_bound_once as reflection_refl_bound_once,
    gen_refl_const_names as reflection_refl_const_names,
    gen_refl_unroll_for as reflection_refl_unroll_for,
    gen_refl_name as reflection_refl_name,
    gen_refl_args as reflection_refl_args,
    gen_refl_has as reflection_refl_has,
    gen_refl_join as reflection_refl_join,
    gen_refl_phi as reflection_refl_phi,
    gen_refl_catch_attr as reflection_refl_catch_attr,
    gen_refl_getattr as reflection_refl_getattr,
    gen_refl_setattr as reflection_refl_setattr,
)
from src.pystachy_compiler.builtins import (
    gen_anyall as builtins_anyall,
    gen_as_list as builtins_as_list,
    gen_bmethod as builtins_bmethod,
    gen_tmethod as builtins_tmethod,
    gen_dict_pairs as builtins_dict_pairs,
    gen_isclose as builtins_isclose,
    gen_prod_seq as builtins_prod_seq,
    gen_prod_item as builtins_prod_item,
    gen_builtin as builtins_builtin,
    gen_call_key as builtins_call_key,
    gen_callable_type as builtins_callable_type,
    gen_consume as builtins_consume,
    gen_dotted as builtins_dotted,
    gen_is_mapcall as builtins_is_mapcall,
    gen_iterator_call as builtins_iterator_call,
    gen_key_check as builtins_key_check,
    gen_key_free as builtins_key_free,
    gen_key_minmax as builtins_key_minmax,
    gen_key_minmax2 as builtins_key_minmax2,
    gen_key_minmax_next as builtins_key_minmax_next,
    gen_key_none as builtins_key_none,
    gen_key_none_join as builtins_key_none_join,
    gen_iter_object as builtins_iter_object,
    gen_key_sort as builtins_key_sort,
    gen_keys_of as builtins_keys_of,
    gen_mapgen as builtins_mapgen,
    gen_modattr as builtins_modattr,
    gen_parse_expr as builtins_parse_expr,
    gen_print_ as builtins_print_,
    gen_next_ as builtins_next_,
    gen_iter_ as builtins_iter_,
    gen_iter_obj as builtins_iter_obj,
    gen_range_fields as builtins_range_fields,
    gen_range_prim as builtins_range_prim,
    gen_walk as builtins_walk,
    gen_pwrite as builtins_pwrite,
    gen_reduce as builtins_reduce,
    gen_reduce_item as builtins_reduce_item,
    gen_reverse_arg as builtins_reverse_arg,
    gen_bytes_ as builtins_bytes_,
    gen_bytes_method as builtins_bytes_method,
    gen_reverse_val as builtins_reverse_val,
    gen_stream_start as builtins_stream_start,
    gen_update as builtins_update,
    gen_vnode as builtins_vnode,
)
from src.pystachy_compiler.calls import (
    gen_adapter as calls_adapter,
    gen_adapter_ret as calls_adapter_ret,
    gen_arity as calls_arity,
    gen_asdict as calls_asdict,
    gen_dc_replace as calls_dc_replace,
    gen_bound as calls_bound,
    gen_cached_wrapper as calls_cached_wrapper,
    gen_getattr_name as calls_getattr_name,
    gen_call as calls_call,
    gen_call_cache as calls_call_cache,
    gen_call_callable as calls_call_callable,
    gen_call_fn as calls_call_fn,
    gen_call_value as calls_call_value,
    gen_callable_pat as calls_callable_pat,
    gen_close_temp as calls_close_temp,
    gen_dispatches as calls_dispatches,
    gen_fname as calls_fname,
    gen_kw_dict as calls_kw_dict,
    gen_kw_list as calls_kw_list,
    gen_kw_method as calls_kw_method,
    gen_kw_record as calls_kw_record,
    gen_kw_repr as calls_kw_repr,
    gen_kw_tuple as calls_kw_tuple,
    gen_kw_type as calls_kw_type,
    gen_method as calls_method,
    gen_method_value as calls_method_value,
    gen_new_obj as calls_new_obj,
    gen_not_callable as calls_not_callable,
    gen_obj_call as calls_obj_call,
    gen_open_ as calls_open_,
    gen_open_call as calls_open_call,
    gen_pat_arg as calls_pat_arg,
    gen_pcoerce as calls_pcoerce,
    gen_print_star as calls_print_star,
    gen_replace as calls_replace,
    gen_nt_make as calls_nt_make,
    gen_nt_new as calls_nt_new,
    gen_star_call as calls_star_call,
    gen_star_who as calls_star_who,
    gen_static_callee as calls_static_callee,
    gen_tests as calls_tests,
    gen_to_callable as calls_to_callable,
    gen_unbound_call as calls_unbound_call,
    gen_virtual_call as calls_virtual_call,
)
from src.pystachy_compiler.containers import (
    gen_affix_any as containers_affix_any,
    gen_bool_find as containers_bool_find,
    gen_dkey as containers_dkey,
    gen_elem_problem as containers_elem_problem,
    gen_fromkeys as containers_fromkeys,
    gen_hash_classes as containers_hash_classes,
    gen_hash_desc as containers_hash_desc,
    gen_hash_kind as containers_hash_kind,
    gen_hash_value as containers_hash_value,
    gen_hashable as containers_hashable,
    gen_iter_elem as containers_iter_elem,
    gen_key_class as containers_key_class,
    gen_key_fx as containers_key_fx,
    gen_key_items as containers_key_items,
    gen_key_kind as containers_key_kind,
    gen_key_problem as containers_key_problem,
    gen_key_repr as containers_key_repr,
    gen_keyed as containers_keyed,
    gen_keys_list as containers_keys_list,
    gen_none_arg as containers_none_arg,
    gen_nonekey as containers_nonekey,
    gen_obj_hash as containers_obj_hash,
    gen_obj_str as containers_obj_str,
    gen_optdefault as containers_optdefault,
    gen_repr as containers_repr,
    gen_sargs as containers_sargs,
    gen_sdiscard as containers_sdiscard,
    gen_set_display as containers_set_display,
    gen_set_new as containers_set_new,
    gen_setop as containers_setop,
    gen_sgen as containers_sgen,
    gen_sitems as containers_sitems,
    gen_siter as containers_siter,
    gen_smethod as containers_smethod,
    gen_stake as containers_stake,
    gen_star_display as containers_star_display,
    gen_star_items as containers_star_items,
    gen_store_elem as containers_store_elem,
    gen_store_key as containers_store_key,
    gen_supdate as containers_supdate,
    gen_to_str as containers_to_str,
)
from src.pystachy_compiler.conversions import (
    gen_num_cast as conversions_num_cast,
    gen_num_cmp as conversions_num_cmp,
    gen_int_ucmp as conversions_int_ucmp,
    gen_ptr_cmp as conversions_ptr_cmp,
    gen_as_float as conversions_as_float,
    gen_as_int as conversions_as_int,
    gen_coerce as conversions_coerce,
    gen_desc as conversions_desc,
    gen_floats as conversions_floats,
    gen_from_slot as conversions_from_slot,
    gen_is_dc as conversions_is_dc,
    gen_isnum as conversions_isnum,
    gen_isref as conversions_isref,
    gen_rarg as conversions_rarg,
    gen_rres as conversions_rres,
    gen_to_slot as conversions_to_slot,
)
from src.pystachy_compiler.declarations import (
    gen_add_field as declarations_add_field,
    gen_alias_ann as declarations_alias_ann,
    gen_alias_args as declarations_alias_args,
    gen_alias_arity as declarations_alias_arity,
    gen_alias_kept as declarations_alias_kept,
    gen_alias_params as declarations_alias_params,
    gen_alias_problem as declarations_alias_problem,
    gen_alias_tvars as declarations_alias_tvars,
    gen_alias_value as declarations_alias_value,
    gen_alias_variadic as declarations_alias_variadic,
    gen_alias_whole as declarations_alias_whole,
    gen_ann as declarations_ann,
    gen_ann_base as declarations_ann_base,
    gen_ann_items as declarations_ann_items,
    gen_ann_none as declarations_ann_none,
    gen_ann_problem as declarations_ann_problem,
    gen_any_in as declarations_any_in,
    gen_boxto as declarations_boxto,
    gen_boxwider as declarations_boxwider,
    gen_class_params as declarations_class_params,
    gen_class_tvars as declarations_class_tvars,
    gen_ctype as declarations_ctype,
    gen_dc_methods as declarations_dc_methods,
    gen_declare_fields as declarations_declare_fields,
    gen_declare_fn as declarations_declare_fn,
    gen_exc_attr as declarations_exc_attr,
    gen_bad_class as declarations_bad_class,
    gen_fgep as declarations_fgep,
    gen_fn_attr_read as declarations_fn_attr_read,
    gen_field as declarations_field,
    gen_frozen as declarations_frozen,
    gen_frozen_store as declarations_frozen_store,
    gen_dc_field as declarations_dc_field,
    gen_dc_fields as declarations_dc_fields,
    gen_dc_factory as declarations_dc_factory,
    gen_is_prop as declarations_is_prop,
    gen_prop_store as declarations_prop_store,
    gen_generic_base as declarations_generic_base,
    gen_getfield as declarations_getfield,
    gen_guess as declarations_guess,
    gen_guess_iter as declarations_guess_iter,
    gen_guess_args as declarations_guess_args,
    gen_has_path as declarations_has_path,
    gen_imported_ref as declarations_imported_ref,
    gen_init_after as declarations_init_after,
    gen_iter_ann as declarations_iter_ann,
    gen_iter_item as declarations_iter_item,
    gen_join as declarations_join,
    gen_none_items as declarations_none_items,
    gen_nt_base as declarations_nt_base,
    gen_nt_class as declarations_nt_class,
    gen_nt_defaults as declarations_nt_defaults,
    gen_nt_dflt_display as declarations_nt_dflt_display,
    gen_nt_dflt_type as declarations_nt_dflt_type,
    gen_nt_fields as declarations_nt_fields,
    gen_opt as declarations_opt,
    gen_optional as declarations_optional,
    gen_path_union as declarations_path_union,
    gen_pathlike as declarations_pathlike,
    gen_scan_fields as declarations_scan_fields,
    gen_guess_varargs as declarations_guess_varargs,
    gen_self_type as declarations_self_type,
    gen_setfield as declarations_setfield,
    gen_shadowed as declarations_shadowed,
    gen_stub as declarations_stub,
    gen_subst as declarations_subst,
    gen_subst_ann as declarations_subst_ann,
    gen_synth as declarations_synth,
    gen_tvar as declarations_tvar,
    gen_typeof as declarations_typeof,
    gen_typevar_def as declarations_typevar_def,
    gen_typevar_in as declarations_typevar_in,
    gen_typing_attr as declarations_typing_attr,
    gen_typing_forms as declarations_typing_forms,
    gen_typing_name as declarations_typing_name,
    gen_typing_ref as declarations_typing_ref,
    gen_unalias as declarations_unalias,
    gen_unalias_all as declarations_unalias_all,
    gen_union_members as declarations_union_members,
    gen_unpack_ann as declarations_unpack_ann,
    gen_vtype as declarations_vtype,
    gen_widens as declarations_widens,
    gen_widens_items as declarations_widens_items,
    gen_wider as declarations_wider,
)
from src.pystachy_compiler.emission import (
    gen_add as emission_add,
    gen_alloc_fixed as emission_alloc_fixed,
    gen_alloca as emission_alloca,
    gen_boxes as emission_boxes,
    gen_br as emission_br,
    gen_cbr as emission_cbr,
    gen_checked as emission_checked,
    gen_convert_at as emission_convert_at,
    gen_convert_in as emission_convert_in,
    gen_converts as emission_converts,
    gen_deref as emission_deref,
    gen_err as emission_err,
    gen_guard as emission_guard,
    gen_hole as emission_hole,
    gen_incoming as emission_incoming,
    gen_iop as emission_iop,
    gen_jump as emission_jump,
    gen_label as emission_label,
    gen_mem_load as emission_mem_load,
    gen_mem_store as emission_mem_store,
    gen_notnone as emission_notnone,
    gen_phi as emission_phi,
    gen_place as emission_place,
    gen_primitive as emission_primitive,
    gen_put as emission_put,
    gen_reboxes as emission_reboxes,
    gen_restore as emission_restore,
    gen_ret_ as emission_ret_,
    gen_returned_none as emission_returned_none,
    gen_rt as emission_rt,
    gen_runtime as emission_runtime,
    gen_save as emission_save,
    gen_sconst as emission_sconst,
    gen_bconst as emission_bconst,
    gen_select as emission_select,
    gen_tmp as emission_tmp,
    gen_unreachable as emission_unreachable,
    gen_unwrap as emission_unwrap,
)
from src.pystachy_compiler.exceptions import (
    gen_as_type as exceptions_as_type,
    gen_assert_fails as exceptions_assert_fails,
    gen_bind_as as exceptions_bind_as,
    gen_catch_set as exceptions_catch_set,
    gen_catches as exceptions_catches,
    gen_cause as exceptions_cause,
    gen_class_defaults as exceptions_class_defaults,
    gen_clause_or as exceptions_clause_or,
    gen_exc_args as exceptions_exc_args,
    gen_exc_brepr as exceptions_exc_brepr,
    gen_exc_class as exceptions_exc_class,
    gen_exc_classes as exceptions_exc_classes,
    gen_exc_helpers as exceptions_exc_helpers,
    gen_exc_isinst as exceptions_exc_isinst,
    gen_exc_keep as exceptions_exc_keep,
    gen_exc_kw as exceptions_exc_kw,
    gen_exc_match as exceptions_exc_match,
    gen_exc_object as exceptions_exc_object,
    gen_exc_of as exceptions_exc_of,
    gen_exc_vals as exceptions_exc_vals,
    gen_exc_value as exceptions_exc_value,
    gen_exc_value_of as exceptions_exc_value_of,
    gen_exit_ as exceptions_exit_,
    gen_exit_value as exceptions_exit_value,
    gen_global_reader as exceptions_global_reader,
    gen_landing as exceptions_landing,
    gen_no_code as exceptions_no_code,
    gen_os_error as exceptions_os_error,
    gen_unicode_error as exceptions_unicode_error,
    gen_raise_ as exceptions_raise_,
    gen_raise_stmt as exceptions_raise_stmt,
    gen_super_call as exceptions_super_call,
    gen_throw as exceptions_throw,
    gen_try_ as exceptions_try_,
    gen_unbind as exceptions_unbind,
    gen_unbinds as exceptions_unbinds,
    gen_unnarrowed as exceptions_unnarrowed,
    gen_unshadow as exceptions_unshadow,
)
from src.pystachy_compiler.expressions import (
    gen_list_hint_type as expressions_list_hint_type,
    gen_argtype as expressions_argtype,
    gen_arith as expressions_arith,
    gen_boolop as expressions_boolop,
    gen_cat as expressions_cat,
    gen_class_attr as expressions_class_attr,
    gen_class_call as expressions_class_call,
    gen_class_ready as expressions_class_ready,
    gen_class_store as expressions_class_store,
    gen_cls_bound as expressions_cls_bound,
    gen_cmp2 as expressions_cmp2,
    gen_titem_eq as expressions_titem_eq,
    gen_cmp_method as expressions_cmp_method,
    gen_concrete_cmp as expressions_concrete_cmp,
    gen_comparable as expressions_comparable,
    gen_numeric_comparable as expressions_numeric_comparable,
    gen_compare as expressions_compare,
    gen_exc_kinds as expressions_exc_kinds,
    gen_cmp_kinds as expressions_cmp_kinds,
    gen_cmp_pick as expressions_cmp_pick,
    gen_inherit_cmp as expressions_inherit_cmp,
    gen_inherit_contains as expressions_inherit_contains,
    gen_member_item as expressions_member_item,
    gen_iter_in as expressions_iter_in,
    gen_concat as expressions_concat,
    gen_cond as expressions_cond,
    gen_conversion as expressions_conversion,
    gen_cvar as expressions_cvar,
    gen_cvar_stores as expressions_cvar_stores,
    gen_dunder as expressions_dunder,
    gen_eqcall as expressions_eqcall,
    gen_exc_eq as expressions_exc_eq,
    gen_exc_id as expressions_exc_id,
    gen_expr as expressions_expr,
    gen_fmt_error as expressions_fmt_error,
    gen_fmt_raise as expressions_fmt_raise,
    gen_format_arg as expressions_format_arg,
    gen_format_args as expressions_format_args,
    gen_format_of as expressions_format_of,
    gen_const_str as expressions_const_str,
    gen_format_dup as expressions_format_dup,
    gen_format_merge as expressions_format_merge,
    gen_format_kw as expressions_format_kw,
    gen_foreign_eq as expressions_foreign_eq,
    gen_forget as expressions_forget,
    gen_forget_walrus as expressions_forget_walrus,
    gen_format_ as expressions_format_,
    gen_has as expressions_has,
    gen_ifexp as expressions_ifexp,
    gen_index as expressions_index,
    gen_isinst as expressions_isinst,
    gen_class_matches as expressions_class_matches,
    gen_obj_isinst as expressions_obj_isinst,
    gen_isinst_reads as expressions_isinst_reads,
    gen_isnone as expressions_isnone,
    gen_isnull as expressions_isnull,
    gen_iter_ret as expressions_iter_ret,
    gen_keep_stack as expressions_keep_stack,
    gen_knownobj as expressions_knownobj,
    gen_list_read as expressions_list_read,
    gen_listcomp as expressions_listcomp,
    gen_lookup_key as expressions_lookup_key,
    gen_narrow_by as expressions_narrow_by,
    gen_narrowable as expressions_narrowable,
    gen_narrows as expressions_narrows,
    gen_no_class_attr as expressions_no_class_attr,
    gen_nonefmt as expressions_nonefmt,
    gen_ntop as expressions_ntop,
    gen_ntup as expressions_ntup,
    gen_numkey as expressions_numkey,
    gen_obj_iter as expressions_obj_iter,
    gen_obj_iterator as expressions_obj_iterator,
    gen_is_iterator as expressions_is_iterator,
    gen_next_type as expressions_next_type,
    gen_optbound as expressions_optbound,
    gen_optcmp as expressions_optcmp,
    gen_optint as expressions_optint,
    gen_percent as expressions_percent,
    gen_percent_opt as expressions_percent_opt,
    gen_pformat as expressions_pformat,
    gen_str_field as expressions_str_field,
    gen_str_fields as expressions_str_fields,
    gen_str_format as expressions_str_format,
    gen_probe_type as expressions_probe_type,
    gen_protocol as expressions_protocol,
    gen_puretype as expressions_puretype,
    gen_richcmp as expressions_richcmp,
    gen_slice_bound as expressions_slice_bound,
    gen_slice_step as expressions_slice_step,
    gen_slice_tuple as expressions_slice_tuple,
    gen_stack_ok as expressions_stack_ok,
    gen_stack_target as expressions_stack_target,
    gen_stack_tuple as expressions_stack_tuple,
    gen_stack_uses as expressions_stack_uses,
    gen_static as expressions_static,
    gen_static_len as expressions_static_len,
    gen_static_reads as expressions_static_reads,
    gen_static_type as expressions_static_type,
    gen_subscript as expressions_subscript,
    gen_tget as expressions_tget,
    gen_tstore as expressions_tstore,
    gen_truth as expressions_truth,
    gen_tuple_ as expressions_tuple_,
    gen_dict_merge as expressions_dict_merge,
    gen_unroll as expressions_unroll,
    gen_pick as expressions_pick,
    gen_iter_static as expressions_iter_static,
    gen_tuple_order as expressions_tuple_order,
    gen_unary as expressions_unary,
)
from src.pystachy_compiler.flow import (
    Flow,
    gen_default_home as flow_default_home,
    gen_fl_defaults as flow_fl_defaults,
    gen_fl_expr as flow_fl_expr,
    gen_fl_fields as flow_fl_fields,
    gen_fl_nested as flow_fl_nested,
    gen_fl_super as flow_fl_super,
    gen_fl_stmt as flow_fl_stmt,
    gen_fl_stmts as flow_fl_stmts,
    gen_fl_target as flow_fl_target,
    gen_flow_body as flow_flow_body,
    gen_flow_function as flow_flow_function,
    gen_flow_program as flow_flow_program,
    gen_scc as flow_scc,
    gen_user_call as flow_user_call,
)
from src.pystachy_compiler.generators import (
    gen_exc_back as generators_exc_back,
    gen_exc_mark as generators_exc_mark,
    gen_pep479 as generators_pep479,
    gen_builtin_catch as generators_builtin_catch,
    gen_gen_ann_ret as generators_gen_ann_ret,
    gen_gen_begin as generators_gen_begin,
    gen_gen_cleanup as generators_gen_cleanup,
    gen_gen_contains as generators_gen_contains,
    gen_gen_unpack as generators_gen_unpack,
    gen_gen_declare as generators_gen_declare,
    gen_gen_drop as generators_gen_drop,
    gen_gen_end as generators_gen_end,
    gen_gen_enter as generators_gen_enter,
    gen_gen_list as generators_gen_list,
    gen_hidden_loop as generators_hidden_loop,
    gen_gen_name as generators_gen_name,
    gen_gen_next as generators_gen_next,
    gen_gen_none_end as generators_gen_none_end,
    gen_none_null as generators_none_null,
    gen_gen_promise as generators_gen_promise,
    gen_gen_ret as generators_gen_ret,
    gen_gen_method as generators_gen_method,
    gen_genexp_value as generators_genexp_value,
    gen_gen_next_value as generators_gen_next_value,
    gen_gen_unhandle as generators_gen_unhandle,
    gen_gen_return as generators_gen_return,
    gen_gen_stream as generators_gen_stream,
    gen_gen_suspend as generators_gen_suspend,
    gen_owned_gen as generators_owned_gen,
    gen_owned_node as generators_owned_node,
    gen_owned_loop as generators_owned_loop,
    gen_yield_from as generators_yield_from,
    gen_yield_stmt as generators_yield_stmt,
    gen_gen_type as generators_gen_type,
    gen_yield_value as generators_yield_value,
    gen_yield_from_proto as generators_yield_from_proto,
    gen_gen_stop as generators_gen_stop,
    gen_gen_raised as generators_gen_raised,
    gen_gen_close as generators_gen_close,
    gen_exc_operand as generators_exc_operand,
    gen_gen_throw_into as generators_gen_throw_into,
    gen_gen_throw as generators_gen_throw,
    gen_gen_send as generators_gen_send,
    gen_yield_from_iter as generators_yield_from_iter,
)
from src.pystachy_compiler.functions import (
    gen_enter as functions_enter,
    gen_extern_args as functions_extern_args,
    gen_externtype as functions_externtype,
    gen_function as functions_function,
    gen_materialize as functions_materialize,
    gen_untold as functions_untold,
)
from src.pystachy_compiler.ir import (
    Blk,
    ClassInfo,
    Closure,
    Data,
    Exit,
    FmtArgs,
    FnInfo,
    Frame,
    IFn,
    Ins,
    IterArg,
    Loop,
    Reduce,
    SeqStart,
    SetArg,
    StopCatch,
    Val,
    Values,
)
from src.pystachy_compiler.ircheck import (
    EffectSummaries,
    gen_bad_ir as ircheck_bad_ir,
    gen_effects as ircheck_effects,
    gen_nums as ircheck_nums,
    gen_opfx as ircheck_opfx,
    gen_verify as ircheck_verify,
    gen_verify_gen as ircheck_verify_gen,
)
from src.pystachy_compiler.lowering import (
    gen_eh_ir as lowering_eh_ir,
    gen_invoke as lowering_invoke,
    gen_lower as lowering_lower,
    gen_lower_ins as lowering_lower_ins,
)
from src.pystachy_compiler.lower_module import (
    gen_cextern as lower_module_cextern,
    gen_dispatch as lower_module_dispatch,
    gen_extern_decl as lower_module_extern_decl,
    gen_gen_module as lower_module_gen_module,
    gen_lower_module as lower_module_lower_module,
    gen_pyext as lower_module_pyext,
)
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.optimizations import (
    gen_addr as optimizations_addr,
    gen_canon as optimizations_canon,
    gen_dictfuse as optimizations_dictfuse,
    gen_disjoint as optimizations_disjoint,
    gen_listget as optimizations_listget,
    gen_optimize as optimizations_optimize,
    gen_preds as optimizations_preds,
    gen_reaching as optimizations_reaching,
    gen_same as optimizations_same,
)
from src.pystachy_compiler.program import (
    gen_body_effect as program_body_effect,
    gen_body_names as program_body_names,
    gen_class_effect as program_class_effect,
    gen_abc_class as program_abc_class,
    gen_abstract_defs as program_abstract_defs,
    gen_generic_aliases as program_generic_aliases,
    gen_abstract_of as program_abstract_of,
    gen_class_problem as program_class_problem,
    gen_decorators as program_decorators,
    gen_derives as program_derives,
    gen_eager as program_eager,
    gen_effect as program_effect,
    gen_exc_base as program_exc_base,
    gen_hook as program_hook,
    gen_inherit as program_inherit,
    gen_accessor as program_accessor,
    gen_class_ref as program_class_ref,
    gen_dc_options as program_dc_options,
    gen_init_template as program_init_template,
    gen_template_fix as program_template_fix,
    gen_left_out as program_left_out,
    gen_makes_tmpl as program_makes_tmpl,
    gen_objects as program_objects,
    gen_partly as program_partly,
    gen_path_of as program_path_of,
    gen_plain as program_plain,
    gen_program as program_program,
    gen_pure as program_pure,
    gen_raisers as program_raisers,
    gen_subclass_problem as program_subclass_problem,
    gen_tmpl_ann as program_tmpl_ann,
    gen_tmpl_of as program_tmpl_of,
)
from src.pystachy_compiler.specs import IROPS
from src.pystachy_compiler.statements import (
    gen_augassign as statements_augassign,
    gen_callable_guard as statements_callable_guard,
    gen_check_import as statements_check_import,
    gen_check_special as statements_check_special,
    gen_class_default as statements_class_default,
    gen_default_problem as statements_default_problem,
    gen_del_name as statements_del_name,
    gen_dflt_fn as statements_dflt_fn,
    gen_early_default as statements_early_default,
    gen_for_ as statements_for_,
    gen_for_range as statements_for_range,
    gen_for_rrange as statements_for_rrange,
    gen_for_seq as statements_for_seq,
    gen_hash_helper as statements_hash_helper,
    gen_hidden as statements_hidden,
    gen_hide as statements_hide,
    gen_hoist as statements_hoist,
    gen_hoist_class as statements_hoist_class,
    gen_imported as statements_imported,
    gen_inplace as statements_inplace,
    gen_iterable as statements_iterable,
    gen_iterarg as statements_iterarg,
    gen_ival as statements_ival,
    gen_leave as statements_leave,
    gen_with_cm as statements_with_cm,
    gen_cm_exits as statements_cm_exits,
    gen_suppress_item as statements_suppress_item,
    gen_loop as statements_loop,
    gen_may_change as statements_may_change,
    gen_no_class_names as statements_no_class_names,
    gen_none_operand as statements_none_operand,
    gen_none_operands as statements_none_operands,
    gen_nonemix as statements_nonemix,
    gen_obj_helpers as statements_obj_helpers,
    gen_objlen as statements_objlen,
    gen_owns as statements_owns,
    gen_range_args as statements_range_args,
    gen_reopt as statements_reopt,
    gen_scan_imports as statements_scan_imports,
    gen_seq_start as statements_seq_start,
    gen_seq_item as statements_seq_item,
    gen_stop_catch as statements_stop_catch,
    gen_next_in as statements_next_in,
    gen_stop_landing as statements_stop_landing,
    gen_stop_classes as statements_stop_classes,
    gen_drain as statements_drain,
    gen_stmt as statements_stmt,
    gen_stmts as statements_stmts,
    gen_str_append as statements_str_append,
    gen_unhashable as statements_unhashable,
    gen_while_ as statements_while_,
)
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.structs import (
    StructFmt,
    gen_struct_call as structs_struct_call,
    gen_struct_format as structs_struct_format,
    gen_struct_helper as structs_struct_helper,
    gen_struct_nodes as structs_struct_nodes,
    gen_struct_pack as structs_struct_pack,
)
from src.pystachy_compiler.templates import (
    gen_bind as templates_bind,
    gen_constructor_unions as templates_constructor_unions,
    gen_fn_sig as templates_fn_sig,
    gen_instance as templates_instance,
    gen_generic_ann as templates_generic_ann,
    gen_generic_hint as templates_generic_hint,
    gen_named_param as templates_named_param,
    gen_named_params as templates_named_params,
    gen_want_params as templates_want_params,
    gen_want_tvars as templates_want_tvars,
    gen_match as templates_match,
    gen_match_items as templates_match_items,
    gen_names_tv as templates_names_tv,
    gen_specialize as templates_specialize,
    gen_literal_class as templates_literal_class,
    gen_literal_args as templates_literal_args,
    gen_lit_context as templates_lit_context,
    gen_const_of as templates_const_of,
    gen_const_fields as templates_const_fields,
)
from src.pystachy_compiler.utils import RtFn, fxmask
from src.pystachy_compiler.variables import (
    gen_adopt as variables_adopt,
    gen_ahead as variables_ahead,
    gen_applies as variables_applies,
    gen_assign as variables_assign,
    gen_unpack_next as variables_unpack_next,
    gen_list_slot as variables_list_slot,
    gen_assigned_to as variables_assigned_to,
    gen_calls_open as variables_calls_open,
    gen_cellvars as variables_cellvars,
    gen_class_ahead as variables_class_ahead,
    gen_closure as variables_closure,
    gen_decides as variables_decides,
    gen_declare as variables_declare,
    gen_deco_callee as variables_deco_callee,
    gen_decorate as variables_decorate,
    gen_fn_names as variables_fn_names,
    gen_lib_fn as variables_lib_fn,
    gen_wrap_names as variables_wrap_names,
    gen_default_want as variables_default_want,
    gen_dry as variables_dry,
    gen_early as variables_early,
    gen_empty as variables_empty,
    gen_empty_of as variables_empty_of,
    gen_fill as variables_fill,
    gen_fill_calls as variables_fill_calls,
    gen_fills as variables_fills,
    gen_first_binding as variables_first_binding,
    gen_fn_value as variables_fn_value,
    gen_foreign as variables_foreign,
    gen_global_var as variables_global_var,
    gen_globread as variables_globread,
    gen_gtype as variables_gtype,
    gen_imp_flag as variables_imp_flag,
    gen_is_global as variables_is_global,
    gen_live_blocks as variables_live_blocks,
    gen_load_name as variables_load_name,
    gen_lookahead as variables_lookahead,
    gen_modchk as variables_modchk,
    gen_modframe as variables_modframe,
    gen_modtype as variables_modtype,
    gen_new_closure as variables_new_closure,
    gen_new_global as variables_new_global,
    gen_no_type as variables_no_type,
    gen_none_ends as variables_none_ends,
    gen_none_read as variables_none_read,
    gen_none_type as variables_none_type,
    gen_none_values as variables_none_values,
    gen_only_empties as variables_only_empties,
    gen_qtype as variables_qtype,
    gen_qualname as variables_qualname,
    gen_read as variables_read,
    gen_read_ahead as variables_read_ahead,
    gen_refine as variables_refine,
    gen_retval as variables_retval,
    gen_rtype as variables_rtype,
    gen_scope_names as variables_scope_names,
    gen_sets as variables_sets,
    gen_slice_assign as variables_slice_assign,
    gen_slice_check as variables_slice_check,
    gen_slice_store as variables_slice_store,
    gen_slice_target as variables_slice_target,
    gen_star_assign as variables_star_assign,
    gen_static_now as variables_static_now,
    gen_static_whole as variables_static_whole,
    gen_store_name as variables_store_name,
    gen_target_type as variables_target_type,
    gen_twin as variables_twin,
    gen_twins as variables_twins,
    gen_type_reads as variables_type_reads,
    gen_typed_empty as variables_typed_empty,
    gen_typed_now as variables_typed_now,
    gen_unbound as variables_unbound,
    gen_unbound_local as variables_unbound_local,
    gen_unfilled as variables_unfilled,
    gen_unpacked as variables_unpacked,
    gen_unready as variables_unready,
    gen_walrus as variables_walrus,
    gen_where_def as variables_where_def,
)


class Gen:
    def __init__(self):
        self.classes: dict[str, ClassInfo] = {}
        self.tmpl: dict[str, bool] = {}  # the class templates (an __init__ parameter without an annotation)
        self.compiling = False  # every declaration is made: code is being compiled (see guess)
        self.specing: dict[str, str] = {}  # the specializations being made, by template and argument types
        self.utags: dict[str, int] = {}
        self.specdone: dict[str, str] = {}  # and those made, which the same call gets again
        self.selfcls = ""  # the class whose method or fields are being declared: what typing.Self is
        self.funcs: dict[str, FnInfo] = {}
        self.aliases: dict[str, str] = {}
        self.imports: dict[str, str] = {}
        self.fglobals: dict[str, bool] = {}
        self.mvars: dict[str, bool] = {}  # module-level variables, also those functions assign
        self.gtypes: dict[str, str] = {}
        self.globs: list[Val] = []
        self.gcroots: list[str] = []
        self.consts: list[Data] = []
        self.bconsts: dict[str, Val] = {}  # builtin module singleton values
        self.strs: dict[str, str] = {}
        self.bstrs: dict[str, str] = {}  # the name of each bytes constant (@b.N), by its bytes
        self.strvals: list[str] = []  # the text of each @s.N
        self.vnodes: list[Val] = []  # the values of "val" nodes, which the compiler makes (vnode)
        self.cmexit = -1  # does a class of the program define __exit__ (1), so that a with block may be skipped (cm_exits)
        # the runtime functions declared, by RUNTIME key, in the order of their first use (which
        # the program's declare lines keep)
        self.rtfns: dict[str, RtFn] = {}
        self.opfxs: dict[str, int] = {}  # the effects of each op of IROPS with fixed effects
        for op in IROPS:
            self.opfxs[op] = fxmask(IROPS[op].replace("T", "").replace("*", ""))
        self.out: list[str] = []
        self.fns: list[IFn] = []  # the functions compiled, in the order they were completed
        self.fll: dict[str, int] = {}  # and their positions there by symbol, once the program is built
        self.summaries = EffectSummaries()
        self.ltype: dict[str, str] = {}
        self.lreg: dict[str, str] = {}
        self.gdecl: dict[str, bool] = {}
        self.assigned: dict[str, bool] = {}
        self.compvars: dict[str, int] = {}
        self.compshare: dict[str, str] = {}  # (the names a comprehension's for clause binds into an earlier clause's variables, and their types)
        self.drying = 0  # (dry() is typing an expression from further on in the function)
        self.loops: list[Loop] = []  # the loops the code being compiled is in, innermost last
        self.exits: list[Exit] = []  # what break, continue and return must do on their way out, innermost last
        self.wdepth: list[int] = []  # len(exits) when each enclosing loop began
        self.handler = ""  # the landing block of the innermost try statement around the code, or ""
        self.excs: list[Val] = []  # the exceptions being handled by the except clauses around it (bare raise)
        self.carried = Val("", "")  # a return's value while leave() runs the finally blocks it leaves
        # the names of except ... as clauses around it that have a variable of their own (another
        # type than the name has outside): [name, its type outside ("": a global), register, flag]
        self.shadows: list[list[str]] = []
        self.xcls: dict[str, bool] = {}  # exception classes whose objects are made: they get an ExcClass
        self.eh = False  # the program has try or with (closed world): exceptions are on (pys_eh_on)
        self.opts: dict[str, bool] = {}  # the optimizations on (optimizations()), once program() starts
        self.lcs: list[str] = []
        self.lct: list[str] = []
        self.lcsoft: list[bool] = []
        self.reds: dict[str, Reduce] = {}  # the reductions (reduce), by the key their items' node holds
        self.ret = "None"
        self.retann = False
        self.nn: dict[str, bool] = {}
        self.selfname = ""
        self.lazy: dict[str, FnInfo] = {}
        self.lazyat: dict[str, int] = {}  # each lazy function's position in lazy, once it is complete
        self.wake: list[int] = []  # a min-heap of the positions of those called and not yet compiled
        self.called: dict[str, bool] = {}
        self.gflag: dict[str, bool] = {}
        self.ocls: dict[str, int] = {}  # classes that appear inside containers: id in descriptors
        self.ocmp: dict[str, bool] = {}  # those of ocls a descriptor compares, not only prints (obj_helpers)
        self.fchk: dict[str, bool] = {}  # the records whose fields desc is checking
        self.hcls: dict[str, bool] = {}  # those of them that keys hash through the program (H<id>: obj_hash)
        self.lenient = False
        self.uflags: dict[str, bool] = {}
        self.lflag: dict[str, str] = {}
        # the names the function appends to (s += t, s = s + t: str_appends), and the "owned" flag
        # of each that is a str local: the slot of an int that is 1 where its str is one an append
        # made and that nothing else holds (see str_append); appending: the append's own read of it
        self.appends: dict[str, bool] = {}
        self.owned: dict[str, str] = {}
        self.appending = False
        # the flags of the names that imports in try statements bind (imp_flag): module code's
        # globals defined so far, and the function's own, each name's slot or cell
        self.impg: dict[str, bool] = {}
        self.iflag: dict[str, str] = {}
        self.modlevel = False
        self.n = 0
        self.cur = "entry"
        self.term = False
        self.line = 0
        self.curfn = FnInfo("<module>", "@main.init", mk("block", "", 0, []), "")
        self.fn = IFn(self.curfn)  # the function being built
        self.blk: Blk = self.fn.blocks[0]  # and its block that code goes to
        # parameters of a template's function whose argument is None, and the line from which one
        # may hold a value of another type: its first binding (none_ends), once compiled the line
        # that gives it that value (see assign, static_type)
        self.nonevars: dict[str, int] = {}
        # the statements that may assign each name, for a variable typed from None (none_type):
        # found once a function needs them (none_sites), then with the key ""
        self.nonesites: dict[str, list[Node]] = {}
        # optional, union and class locals: the narrower type a read has here (see narrows)
        self.narrowed: dict[str, str] = {}
        self.nonecmp = False  # the read being compiled is compared with None (see none_type)
        self.anyopt = False  # an optional, union or class local exists: narrows has work to do
        self.building: dict[str, bool] = {}  # the functions being compiled
        self.wide: dict[str, bool] = {}  # optional values read from a global or a field (function + register), which no test narrows
        self.soft = Node("", "", 0)  # a display compared with a value: what it holds widens the type expected of it (see wider)
        self.nokey = Node("", "", 0)
        self.stkkey = self.nokey  # a tuple display that a lookup takes as its key (lookup_key): made in the frame
        self.retseen: dict[str, bool] = {}  # templates' functions a call used the return type of while they were compiled
        self.branch = 0  # how many if branches and loop bodies enclose the code being compiled
        self.making: list[str] = []  # the template functions being compiled, each with its call site
        self.template_bytes = 0  # bytes in the signatures of the active instance() calls
        self.template_instances = 0  # retained instances in this compilation, including completed ones
        self.template_retained = 0  # and the bytes of their signatures
        self.retainers: dict[str, int] = {}  # and those of each template, by the name messages give it
        self.unsupported: dict[str, str] = {}  # classes of imported modules that cannot be compiled: why
        self.cnodes: dict[int, Node] = {}  # every module-level class or subclass statement, by line
        self.hooks: dict[str, str] = {}  # see hook()
        self.chooks: dict[int, str] = {}
        self.flagged: dict[str, bool] = {}  # globals whose "is assigned" flag effect() reads
        self.unraised: dict[str, bool] = {}  # the modules where a class left out held an operation that may raise, not evaluated (left_out)
        self.noneglobals: dict[str, bool] = {}  # module globals of imported modules that are always None
        self.intglobals: dict[str, str] = {}  # single-binding module int literals, after normal read checks
        self.rangeused = False  # code addresses an object of lib's range class (declared then: lower_module)
        self.intat: dict[str, int] = {}  # the line of each constant's own binding (including from-imports)
        self.strglobals: dict[str, str] = {}  # single-binding module str literals: formats for str.format()
        self.strtuples: dict[str, list[str]] = {}  # and tuples of them: functools.wraps()'s assigned
        self.abstracts: dict[str, list[str]] = {}  # each class's own @abstractmethod methods (abstract_defs)
        self.abcmeta: dict[str, bool] = {}  # the classes whose statements pass metaclass=ABCMeta
        # each module's TYPE_CHECKING that is a constant False (false_flag()), and its names that hold a
        # test of the platform (Loader.platform_flags()): the literal each holds, "False" or "True"
        self.constflags: dict[str, str] = {}
        # an imported module's globals (and defs and classes) that other code may find unbound:
        # not assigned on every path through its module code, or before an import that may run
        # code calling back into the module
        self.late: dict[str, bool] = {}
        self.lib = False  # declaring an imported module's function: what it cannot compile is an error only where it is called
        self.ext = ""  # pystachy ext: the name of the CPython extension module the program becomes
        self.libdir = ""  # the lib/ beside the compiler, the last directory of the module path (lib_fn)
        self.csyms: dict[str, str] = {}  # @ffi.extern: each C symbol's declare (one signature per program)
        self.csymline: dict[str, int] = {}  # and the line that declared it
        self.extvars: dict[str, int] = {}  # pystachy ext: the main module's variables, and the line that binds each
        self.unicode_audit = os.getenv("PYSTACHY_UNICODE_AUDIT", "") == "1"
        self.rtmode = False  # compiling runtime.py: its pys_* functions join runtime.c's under their C names (see runtime_ir)
        self.rtdefs: dict[str, FnInfo] = {}  # runtime mode: the pys_* functions this module defines, by C name
        self.rtcache = False  # runtime mode, for the driver's runtime cache: PYSTACHY_IRFX is the program's
        self.externs: dict[str, str] = {}  # runtime mode: runtime.c's functions runtime.py declares (def f(...) -> T: ...), by symbol: their declare line ("" if RUNTIME's)
        self.deps: dict[str, str] = {}  # the modules each module's top-level code imports, space-separated
        self.comp: dict[str, str] = {}  # each module's strongly connected component of that graph (one of its modules)
        self.flowmod = ""
        self.flowctx: dict[str, list[dict[str, bool]]] = {}  # module globals, safe bindings and deletions for lazy method flow
        self.fvars: dict[str, bool] = {}  # the module's variables that its code so far has made functions (name = f: user_call)
        self.flowlater: list[Node] = []  # the bodies of module code's lambdas, analysed once flowctx has the module's (fl_nested)
        # the defs and lambdas inside functions, each as one function (an instance) compiles it: by
        # "<that function's symbol> <the node>" (closure_key), their position in closures
        self.closures: list[Closure] = []
        self.clokeys: dict[str, int] = {}
        self.cells: dict[str, str] = {}  # the function's variables that closures take: the cell of each (a pointer)
        self.adapters: dict[str, str] = {}  # "<function value type> <Callable type>" -> its adapter's symbol (Gen.adapter)
        self.adrets: dict[str, str] = {}  # "<function value type> <parameter types>" -> what it returns (Gen.adapter_ret)
        self.ncv = 0  # the adapters named (@cv.N), each before its body is compiled, which may name others
        self.cacheforms: dict[str, int] = {}  # cached calls: positional count and ordered keyword names
        self.decorated: dict[str, bool] = {}  # the defs of a module's top level that bind what their decorators give (decorate)
        self.decoexprs: dict[str, Node] = {}  # "<module> <line>" -> the dotted name of the decorator there (deco_callee)
        self.cvos: dict[str, bool] = {}  # the constant Callable objects defined (Gen.to_callable)
        self.nlw: dict[str, bool] = {}  # and those of them, or of the variables it takes, that a closure assigns (nonlocal)
        # the generator object a call of a generator function made last (the call's value), and that
        # function (Gen.call_fn): a loop over that value owns the generator (owned_gen)
        self.gencall = ""
        self.gencallf: FnInfo | None = None
        self.ngenexp = 0  # the generator expressions made values (genexp_value): each a function of its own
        self.vowned: dict[str, FnInfo] = {}  # val nodes of such generators (owned_node), by the node's text
        self.gendrops = False  # a gen.drop op was lowered: the module defines its helper (lower_module)
        # the program uses the generator protocol's send() or throw(), or the value of a yield
        # (generators.uses_protocol, closed world): its generators' promises hold what is sent and
        # thrown, and their yields take them (docs/internals.md#generators)
        self.gproto = False
        # the program reads the exception being handled, sys.exception() (generators.reads_handled):
        # a generator's try statements tell its own from its resumer's (exc_mark, exc_back)
        self.excread = False
        # the program reads an exception's __cause__ (generators.reads_cause): raise ... from c
        # and PEP 479's RuntimeError record it (pys_exc_setcause)
        self.causeread = False
        self.stmtexpr: Node | None = None  # the expression of the expression statement being compiled
        self.mcall: Node | None = None  # the call o.m(...) whose method Gen.method is compiling (close())
        self.coros = False  # a generator function was lowered: the module declares LLVM's coroutine intrinsics
        self.lowblk = ""  # the label of the block being lowered (gen.start's phi names it)
        self.elsekids: list[Node] = []  # the body of a for/while ... else loop being compiled
        self.elsebrk = ""  # and the label after its else block
        self.brks: list[list[dict[str, str]]] = []  # for each loop being compiled, what narrowed holds at its breaks
        self.elsebrks: list[dict[str, str]] = []  # those of the last loop with an else block
        # empty [] and {} assigned to a variable without a type: its type has "?" until a use shows
        # what the container holds (see fill). The op that makes one holds a hole, which gets that
        # type (lowering prints a dict's key kind from it)
        self.allowq = False  # the read being compiled may see such a type (len(), a truth test)
        self.lkk: dict[str, str] = {}  # a local's holes, space-separated
        self.gkk: dict[str, str] = {}  # a global's
        self.holes: list[str] = [""]  # each hole's type, "" until a use shows it (0: no hole)
        # globals that hold the same empty container (X = Y at module level), one type: each one's
        # class of twins (named by a member), and each class's members
        self.twin_of: dict[str, str] = {}
        self.twin_set: dict[str, list[str]] = {}
        self.origin: dict[str, str] = {}  # X -> Y for those, where an annotation of the container belongs
        # code compiled before module code assigns what it reads (a template's function called
        # early, a function compiled early for a global's type: see ahead and early)
        self.inits: dict[str, FnInfo] = {}  # each module's top-level code, by module name
        self.mfile: dict[str, str] = {}  # each module's file, by module name
        self.compiled: dict[str, bool] = {}  # the functions compiled so far, by their LLVM name
        self.busy: dict[str, bool] = {}  # the globals ahead() is typing
        self.pending: dict[str, bool] = {}  # default values' globals declared before their def or class statement
        # compiling a from-import of a global its module may leave unbound when the import runs:
        # CPython would raise ImportError, with the module's path, and Pystachy raises AttributeError,
        # so the global must have its type already (no ahead, early or twins)
        self.copying = False
        self.live = False  # fills skips the loops over the empty tuple too (see unfilled)
        self.dead = False  # and found a fill there, or in a branch a static test removes
        self.whole = 0  # static() for the if at this line that fills searches, -1 for none_ends
        self.unsure = False  # and a type not known yet left the test undecided (see static_type)
        # a template's function returning such an empty container without a type (see retval):
        # the locals it returns so, space-separated, by its LLVM name, and the functions whose
        # return type of that kind a call has used, so that it can no longer change (see adopt)
        self.qret: dict[str, str] = {}
        self.qholes: dict[str, list[int]] = {}  # direct/forwarded empty returns' layout holes, typed by adopt
        self.qused: dict[str, str] = {}  # layouts already consumed by recursive calls
        self.qforward: dict[str, bool] = {}  # open returns include a forwarded empty result
        self.inited: dict[str, bool] = {}  # the modules whose top-level code is compiled
        self.guessed: dict[str, str] = {}  # by function: why such a container is list[int] or dict[int, int] there, for a type error
        self.galias: dict[str, bool] = {}  # the classes whose body binds __class_getitem__ = classmethod(GenericAlias) (generic_aliases)
        self.nts: dict[str, bool] = {}  # the typing.NamedTuple classes: a dataclass whose fields cannot be assigned (see nt_class)
        self.cnts: dict[str, Node] = {}  # those namedtuple() makes, class templates: their "namedtuple" nodes (Loader.nt_class)
        self.ntdflts: dict[str, str] = {}  # the type of each one's _field_defaults, once its global is declared (nt_defaults)
        self.hasfrozen = False  # a @dataclass(frozen=True) class: except clauses list dataclasses.FrozenInstanceError
        self.scanning: dict[str, bool] = {}  # the properties whose setters scan_fields is scanning (C.x)
        # "C.x": class attribute x of plain class C, which the program assigns through the class
        # (C.x = v, cls.x += 1): a global that objects read until they assign x (see cvar_stores)
        self.cvars: dict[str, bool] = {}
        self.typevars: list[str] = []  # module globals bound to typing.TypeVar(...) or TypeVarTuple(...), which only annotations may name
        self.tvtuples: dict[str, bool] = {}  # those bound to a TypeVarTuple, which an annotation unpacks (*Ts)
        self.tvdefaults: dict[str, bool] = {}  # and those with a default (TypeVar("T", default=...), class C[T = int])
        # the generic classes (class C(Generic[T, *Ts]) and class C[T, *Ts]): their type variables,
        # which the arguments of the call that makes an object bind (see bind)
        self.tparams: dict[str, list[str]] = {}
        self.pep695: dict[str, bool] = {}  # the generic classes of PEP 695's syntax, class C[T] (reflection: __type_params__)
        # the type aliases, by qualified name: the statement that binds each (Mod.taliases), and
        # those whose annotation alias_ann is making the type of
        self.taliases: dict[str, Node] = {}
        self.resolving: list[str] = []
        self.unaliased = 0  # (the nodes unalias has made of the annotation it expands)
        self.reflrecs: dict[str, Data] = {}  # the reflection records made (refl_record), by global name
        self.reflstores: dict[str, bool] = {}  # the attribute names the program's assignments assign (refl_stored)
        self.refllate: dict[str, bool] = {}  # those assigned other than by an __init__ through its object (refl_late)
        self.refltexts: list[RText] = []  # the deferred texts of reflective lookups (refl_defer)
        self.reflcopies = 1  # the copies of the code being compiled that unrolled loops make (refl_unroll_for)

    # ---- reflection (reflection.py)
    def refl_typeof(self, n: Node) -> Node | None:
        return reflection_refl_typeof(self, n)

    def refl_concrete(self, t: str) -> list[str]:
        return reflection_refl_concrete(self, t)

    def refl_may_none(self, v: Val) -> bool:
        return reflection_refl_may_none(self, v)

    def refl_split(self, v: Val, nonnull: bool = False) -> list[RLeaf]:
        return reflection_refl_split(self, v, nonnull)

    def refl_split_class(self, v: Val) -> list[RLeaf]:
        return reflection_refl_split_class(self, v)

    def refl_type_name(self, c: str, what: str) -> str:
        return reflection_refl_type_name(self, c, what)

    def refl_record(self, c: str) -> str:
        return reflection_refl_record(self, c)

    def refl_type_of(self, v: Val, what: str, nonnull: bool = False) -> list[RLeaf]:
        return reflection_refl_type_of(self, v, what, nonnull)

    def refl_class_of(self, v: Val, nonnull: bool = False) -> Val:
        return reflection_refl_class_of(self, v, nonnull)

    def refl_type_attr(self, x: Node, what: str) -> Val:
        return reflection_refl_type_attr(self, x, what)

    def refl_type_operand(self, n: Node) -> str:
        return reflection_refl_type_operand(self, n)

    def refl_type_cmp(self, n: Node) -> Val | None:
        return reflection_refl_type_cmp(self, n)

    def refl_name(self, n: Node) -> str:
        return reflection_refl_name(self, n)

    def refl_args(self, name: str, args: list[Node], lo: int, hi: int) -> None:
        return reflection_refl_args(self, name, args, lo, hi)

    def refl_has(self, c: str, a: str) -> str:
        return reflection_refl_has(self, c, a)

    def refl_join(self, vals: list[Val], what: str) -> str:
        return reflection_refl_join(self, vals, what)

    def refl_phi(self, vals: list[Val], blocks: list[str], end: str, what: str) -> Val:
        return reflection_refl_phi(self, vals, blocks, end, what)

    def refl_catch_attr(self, x: Val, a: str, d: Val, vals: list[Val], blocks: list[str], end: str, truth: bool = False) -> None:
        return reflection_refl_catch_attr(self, x, a, d, vals, blocks, end, truth)

    def refl_getattr(self, args: list[Node], want: str) -> Val:
        return reflection_refl_getattr(self, args, want)

    def refl_setattr(self, args: list[Node]) -> Val:
        return reflection_refl_setattr(self, args)

    def refl_bound_once(self, name: str) -> list[str] | None:
        return reflection_refl_bound_once(self, name)

    def refl_const_names(self, it: Node) -> list[str] | None:
        return reflection_refl_const_names(self, it)

    def refl_unroll_for(self, n: Node) -> bool:
        return reflection_refl_unroll_for(self, n)

    def refl_supported(self, c: str, what: str) -> None:
        return reflection_refl_supported(self, c, what)

    def refl_defines(self, c: str, m: str) -> bool:
        return reflection_refl_defines(self, c, m)

    def refl_names(self, c: str) -> list[list[str]]:
        return reflection_refl_names(self, c)

    def refl_listed(self, c: str, nk: list[str]) -> bool:
        return reflection_refl_listed(self, c, nk)

    def refl_public(self, c: str, n: str) -> None:
        return reflection_refl_public(self, c, n)

    def refl_init_order(self, c: str, f: FnInfo, out: list[str], maybe: dict[str, bool]) -> bool:
        return reflection_refl_init_order(self, c, f, out, maybe)

    def refl_dict_order(self, c: str) -> list[str]:
        return reflection_refl_dict_order(self, c)

    def refl_stored(self, name: str) -> bool:
        return reflection_refl_stored(self, name)

    def refl_late(self, name: str) -> bool:
        return reflection_refl_late(self, name)

    def refl_fields_table(self, c: str) -> str:
        return reflection_refl_fields_table(self, c)

    def refl_layout_record(self, c: str) -> str:
        return reflection_refl_layout_record(self, c)

    def refl_dict_of(self, n: Node) -> Node | None:
        return reflection_refl_dict_of(self, n)

    def refl_vars_text(self, o: Val, known: bool) -> Val:
        return reflection_refl_vars_text(self, o, known)

    def refl_textual(self, n: Node) -> bool:
        return reflection_refl_textual(self, n)

    def refl_defer(self, n: Node) -> Val:
        return reflection_refl_defer(self, n)

    def refl_finish(self, v: Val, conv: str) -> Val:
        return reflection_refl_finish(self, v, conv)

    def refl_dict_operand(self, n: Node, x: Node) -> Val:
        return reflection_refl_dict_operand(self, n, x)

    def refl_unroll_dict(self, n: Node, d: Node, x: Node, m: str) -> None:
        return reflection_refl_unroll_dict(self, n, d, x, m)

    def refl_size_check(self, ov: Val, flagged: list[str], snap: list[str]) -> None:
        return reflection_refl_size_check(self, ov, flagged, snap)

    def refl_dir_names(self, c: str) -> list[list[str]]:
        return reflection_refl_dir_names(self, c)

    def refl_dir(self, x: Node) -> Val:
        return reflection_refl_dir(self, x)

    def refl_dir_of(self, it: Node) -> Node | None:
        return reflection_refl_dir_of(self, it)

    def refl_dict_copy(self, d: Node) -> Val:
        return reflection_refl_dict_copy(self, d)

    def refl_dict_format(self, d: Node, keys: list[str], fmt: str, what: str) -> Val:
        return reflection_refl_dict_format(self, d, keys, fmt, what)

    def refl_percent(self, fmt: str, d: Node) -> Val:
        return reflection_refl_percent(self, fmt, d)

    def refl_format_map(self, fmt: str, d: Node) -> Val:
        return reflection_refl_format_map(self, fmt, d)

    def refl_dc_class(self, x: Node, what: str) -> str:
        return reflection_refl_dc_class(self, x, what)

    def refl_dc_check(self, t: str, what: str) -> str:
        return reflection_refl_dc_check(self, t, what)

    def refl_dc_names(self, it: Node) -> list[str] | None:
        return reflection_refl_dc_names(self, it)

    def refl_unroll_fields(self, n: Node, names: list[str]) -> None:
        return reflection_refl_unroll_fields(self, n, names)

    def refl_dc_type(self, t: str, what: str, seen: list[str]) -> str:
        return reflection_refl_dc_type(self, t, what, seen)

    def refl_dc_copy(self, v: Val, what: str, seen: list[str], nonnull: bool = False) -> Val:
        return reflection_refl_dc_copy(self, v, what, seen, nonnull)

    def refl_dataclasses(self, name: str, args: list[Node]) -> Val:
        return reflection_refl_dataclasses(self, name, args)

    def refl_union_str(self, v: Val, m: str) -> Val:
        return reflection_refl_union_str(self, v, m)

    def refl_name_list(self, c: str) -> list[list[str]]:
        return reflection_refl_name_list(self, c)

    def refl_names_table(self, c: str) -> str:
        return reflection_refl_names_table(self, c)

    def refl_runtime_name(self, a: Node, what: str) -> Val:
        return reflection_refl_runtime_name(self, a, what)

    def refl_find(self, c: str, name: Val) -> str:
        return reflection_refl_find(self, c, name)

    def refl_hasattr(self, args: list[Node]) -> Val:
        return reflection_refl_hasattr(self, args)

    def refl_otext(self, c: str, name: str) -> str:
        return reflection_refl_otext(self, c, name)

    def refl_lookup(self, n: Node) -> RText:
        return reflection_refl_lookup(self, n)

    def refl_lookup_text(self, r: RText, conv: str) -> Val:
        return reflection_refl_lookup_text(self, r, conv)

    def refl_arm_text(self, r: RText, arm: RArm, conv: str) -> Val:
        return reflection_refl_arm_text(self, r, arm, conv)

    def refl_setattr_runtime(self, args: list[Node]) -> Val:
        return reflection_refl_setattr_runtime(self, args)

    def refl_replace_changes(self, obj: Node, d: Val) -> None:
        return reflection_refl_replace_changes(self, obj, d)

    def refl_hasattr_lit(self, o: Val, a: str, known: bool) -> Val:
        return reflection_refl_hasattr_lit(self, o, a, known)

    def refl_prop_in(self, t: str, a: str) -> bool:
        return reflection_refl_prop_in(self, t, a)

    def refl_derived_only(self, x: Node, a: str) -> bool:
        return reflection_refl_derived_only(self, x, a)

    # ---- emission helpers
    def err(self, msg: str) -> None:
        return emission_err(self, msg)

    def save(self) -> Frame:
        return emission_save(self)

    def restore(self, fr: Frame) -> None:
        return emission_restore(self, fr)

    def tmp(self) -> str:
        return emission_tmp(self)

    def label(self) -> str:
        return emission_label(self)


    def add(self, i: Ins) -> None:
        return emission_add(self, i)

    def put(self, i: Ins, k: int) -> None:
        return emission_put(self, i, k)


    def scalar(self, op: str, args: list[Val], flags: str = "") -> str:
        return scalar_ir_scalar(self, op, args, flags)

    def scalar_cast(self, op: str, a: Val, t: str) -> str:
        return scalar_ir_scalar_cast(self, op, a, t)

    def scalar_cmp(self, predicate: str, a: Val, b: Val) -> str:
        return scalar_ir_scalar_cmp(self, predicate, a, b)

    def lower_scalar(self, i: Ins) -> None:
        return scalar_ir_lower_scalar(self, i)

    def verify_scalar(self, fn: IFn, b: Blk, i: Ins) -> None:
        return scalar_ir_verify_scalar(self, fn, b, i)

    def mload(self, t: str, p: str, metadata: str = "") -> str:
        return memory_ir_mload(self, t, p, metadata)

    def mstore(self, t: str, v: str, p: str, metadata: str = "") -> None:
        memory_ir_mstore(self, t, v, p, metadata)

    def maddr(self, t: str, p: str, index: str, inbounds: bool = False) -> str:
        return memory_ir_maddr(self, t, p, index, inbounds)

    def mem_load(self, a: Val) -> Val:
        return emission_mem_load(self, a)

    def mem_store(self, a: Val, v: Val) -> None:
        return emission_mem_store(self, a, v)

    def place(self, l: str) -> None:
        return emission_place(self, l)

    def jump(self, l: str) -> None:
        return emission_jump(self, l)

    def br(self, l: str) -> None:
        return emission_br(self, l)

    def cbr(self, c: str, a: str, b: str) -> None:
        return emission_cbr(self, c, a, b)

    def ret_(self, v: Val) -> None:
        return emission_ret_(self, v)

    def returned_none(self) -> bool:
        return emission_returned_none(self)

    def unreachable(self) -> None:
        return emission_unreachable(self)

    def incoming(self, ph: Ins, v: str, l: str) -> None:
        return emission_incoming(self, ph, v, l)

    def phi(self, ph: Ins) -> str:
        return emission_phi(self, ph)

    def select(self, c: str, x: Val, y: Val) -> str:
        return emission_select(self, c, x, y)

    def rt(self, name: str, ret: str, args: list[str], x: str = "") -> str:
        return emission_rt(self, name, ret, args, x)

    def alloc_fixed(self, t: str) -> Val:
        return emission_alloc_fixed(self, t)

    def runtime(self, name: str) -> str:
        return emission_runtime(self, name)

    def hole(self, kind: str) -> Ins:
        return emission_hole(self, kind)

    def checked(self, op: str, a: str, b: str) -> list[str]:
        return emission_checked(self, op, a, b)

    def guard(self, bad: str, msg: str) -> None:
        return emission_guard(self, bad, msg)

    def primitive(self, name: str, vals: list[Val]) -> Val:
        return emission_primitive(self, name, vals)

    def iop(self, op: str, a: str, b: str) -> str:
        return emission_iop(self, op, a, b)

    def notnone(self, v: Val, msg: str) -> None:
        return emission_notnone(self, v, msg)

    def unwrap(self, v: Val, msg: str) -> Val:
        return emission_unwrap(self, v, msg)

    def deref(self, v: Val) -> Val:
        return emission_deref(self, v)

    def reboxes(self, a: str, b: str) -> bool:
        return emission_reboxes(self, a, b)

    def convert_at(self, v: Val, t: str, label: str) -> Val:
        return emission_convert_at(self, v, t, label)

    def converts(self, a: str, b: str) -> bool:
        return emission_converts(self, a, b)

    def boxes(self, a: str, b: str) -> bool:
        return emission_boxes(self, a, b)

    def convert_in(self, v: Val, t: str, blk: Blk) -> Val:
        return emission_convert_in(self, v, t, blk)

    def sconst(self, s: str) -> str:
        return emission_sconst(self, s)

    def bconst(self, s: str) -> str:
        return emission_bconst(self, s)

    def alloca(self, t: str, name: str) -> str:
        return emission_alloca(self, t, name)

    def to_slot(self, v: Val) -> str:
        return conversions_to_slot(self, v)

    def from_slot(self, s: str, t: str) -> Val:
        return conversions_from_slot(self, s, t)

    def rarg(self, v: Val) -> str:
        return conversions_rarg(self, v)

    def rres(self, r: str, t: str) -> Val:
        return conversions_rres(self, r, t)

    def as_int(self, v: Val) -> Val:
        return conversions_as_int(self, v)

    def as_float(self, v: Val) -> Val:
        return conversions_as_float(self, v)

    def num_cast(self, v: Val, t: str) -> Val:
        return conversions_num_cast(self, v, t)

    def num_cmp(self, op: str, a: Val, b: Val) -> Val:
        return conversions_num_cmp(self, op, a, b)

    def int_ucmp(self, op: str, a: Val, b: Val) -> Val:
        return conversions_int_ucmp(self, op, a, b)

    def ptr_cmp(self, op: str, a: Val, b: Val) -> Val:
        return conversions_ptr_cmp(self, op, a, b)

    def floats(self, v: Val) -> Val:
        return conversions_floats(self, v)

    def is_dc(self, t: str) -> bool:
        return conversions_is_dc(self, t)

    def isnum(self, t: str) -> bool:
        return conversions_isnum(self, t)

    def isref(self, t: str) -> bool:
        return conversions_isref(self, t)

    def coerce(self, v: Val, t: str, what: str='') -> Val:
        return conversions_coerce(self, v, t, what)

    def desc(self, t: str, use: str) -> str:
        return conversions_desc(self, t, use)

    def ctype(self, base: str, ts: list[str]) -> str:
        return declarations_ctype(self, base, ts)

    def none_items(self, t: str) -> str:
        return declarations_none_items(self, t)

    def subst(self, t: str, T: str, K: str, V: str, S: str) -> str:
        return declarations_subst(self, t, T, K, V, S)

    def typeof(self, n: Node) -> str:
        return declarations_typeof(self, n)

    def ann(self, n: Node) -> str:
        return declarations_ann(self, n)

    def ann_base(self, b: Node) -> str:
        return declarations_ann_base(self, b)

    def ann_none(self, n: Node, seen: list[str]) -> bool:
        return declarations_ann_none(self, n, seen)

    def ann_items(self, xs: list[Node]) -> list[str]:
        return declarations_ann_items(self, xs)

    def unpack_ann(self, n: Node) -> str:
        return declarations_unpack_ann(self, n)

    def tvar(self, s: str) -> str:
        return declarations_tvar(self, s)

    def self_type(self) -> str:
        return declarations_self_type(self)

    def pathlike(self, n: Node) -> bool:
        return declarations_pathlike(self, n)

    def imported_ref(self, n: Node) -> str:
        return declarations_imported_ref(self, n)

    def union_members(self, n: Node, out: list[Node]) -> list[Node]:
        return declarations_union_members(self, n, out)

    def has_path(self, n: Node) -> bool:
        return declarations_has_path(self, n)

    def path_union(self, ms: list[Node]) -> str:
        return declarations_path_union(self, ms)

    def typevar_def(self, st: Node) -> bool:
        return declarations_typevar_def(self, st)

    def typevar_in(self, anns: list[Node], skip: list[str]) -> str:
        return declarations_typevar_in(self, anns, skip)

    def any_in(self, anns: list[Node]) -> bool:
        return declarations_any_in(self, anns)

    def class_tvars(self, cls: str) -> list[str]:
        return declarations_class_tvars(self, cls)

    def class_params(self, st: Node) -> str:
        return declarations_class_params(self, st)

    def alias_value(self, name: str) -> Node:
        return declarations_alias_value(self, name)

    def alias_params(self, name: str) -> list[str]:
        return declarations_alias_params(self, name)

    def alias_whole(self, name: str) -> Node:
        return declarations_alias_whole(self, name)

    def alias_problem(self, e: Node) -> str:
        return declarations_alias_problem(self, e)

    def alias_args(self, name: str, n: int) -> str:
        return declarations_alias_args(self, name, n)

    def alias_arity(self, name: str, tps: list[str], n: int) -> str:
        return declarations_alias_arity(self, name, tps, n)

    def alias_tvars(self, a: Node, out: list[str], seen: list[str]) -> None:
        return declarations_alias_tvars(self, a, out, seen)

    def alias_variadic(self, name: str) -> bool:
        return declarations_alias_variadic(self, name)

    def alias_kept(self, name: str) -> bool:
        return declarations_alias_kept(self, name)

    def unalias(self, a: Node, seen: list[str]) -> Node:
        return declarations_unalias(self, a, seen)

    def subst_ann(self, n: Node, tps: list[str], args: list[Node]) -> Node:
        return declarations_subst_ann(self, n, tps, args)

    def alias_ann(self, n: Node) -> str:
        return declarations_alias_ann(self, n)

    def unalias_all(self, n: Node) -> None:
        return declarations_unalias_all(self, n)

    def ann_problem(self, n: Node, ret: bool) -> str:
        return declarations_ann_problem(self, n, ret)

    def vtype(self, n: Node) -> str:
        return declarations_vtype(self, n)

    def typing_attr(self, n: Node) -> str:
        return declarations_typing_attr(self, n)

    def typing_ref(self, n: Node) -> str:
        return declarations_typing_ref(self, n)

    def typing_forms(self, m: Mod, body: list[Node], cls: bool) -> list[Node]:
        return declarations_typing_forms(self, m, body, cls)

    def stub(self, m: Mod, st: Node) -> bool:
        return declarations_stub(self, m, st)

    def typing_name(self, s: str) -> str:
        return declarations_typing_name(self, s)

    def opt(self, t: str, x: Node) -> str:
        return declarations_opt(self, t, x)

    def optional(self, t: str) -> str:
        return declarations_optional(self, t)

    def join(self, a: str, b: str) -> str:
        return declarations_join(self, a, b)

    def wider(self, a: str, b: str) -> str:
        return declarations_wider(self, a, b)

    def boxwider(self, a: str, b: str) -> str:
        return declarations_boxwider(self, a, b)

    def boxto(self, v: Val, t: str) -> Val:
        return declarations_boxto(self, v, t)

    def widens(self, a: str, b: str) -> bool:
        return declarations_widens(self, a, b)

    def widens_items(self, a: str, b: str) -> bool:
        return declarations_widens_items(self, a, b)

    def declare_fn(self, d: Node, cls: str, inherited: bool=False) -> FnInfo:
        return declarations_declare_fn(self, d, cls, inherited)

    def iter_ann(self, n: Node) -> str:
        return declarations_iter_ann(self, n)

    def iter_item(self, n: Node) -> Node:
        return declarations_iter_item(self, n)

    def exc_attr(self, ci: ClassInfo, name: str) -> None:
        return declarations_exc_attr(self, ci, name)

    def bad_class(self, ci: ClassInfo, why: str) -> None:
        return declarations_bad_class(self, ci, why)

    def shadowed(self, ci: ClassInfo, name: str) -> bool:
        return declarations_shadowed(self, ci, name)

    def init_after(self, ci: ClassInfo, name: str) -> bool:
        return declarations_init_after(self, ci, name)

    def add_field(self, ci: ClassInfo, name: str, t: str) -> None:
        return declarations_add_field(self, ci, name, t)

    def declare_fields(self, ci: ClassInfo) -> None:
        return declarations_declare_fields(self, ci)

    def nt_class(self, ci: ClassInfo) -> None:
        return declarations_nt_class(self, ci)

    def generic_base(self, n: Node) -> list[str]:
        return declarations_generic_base(self, n)

    def nt_base(self, n: Node) -> bool:
        return declarations_nt_base(self, n)

    def nt_fields(self, c: str) -> list[str]:
        return declarations_nt_fields(self, c)

    def nt_defaults(self, c: str) -> Val:
        return declarations_nt_defaults(self, c)

    def nt_dflt_display(self, c: str) -> Node:
        return declarations_nt_dflt_display(self, c)

    def nt_dflt_type(self, c: str) -> str:
        return declarations_nt_dflt_type(self, c)

    def frozen(self, t: str, name: str) -> None:
        return declarations_frozen(self, t, name)

    def frozen_store(self, o: Val, name: str, delete: bool=False) -> bool:
        return declarations_frozen_store(self, o, name, delete)

    def dc_field(self, ci: ClassInfo, st: Node) -> None:
        return declarations_dc_field(self, ci, st)

    def dc_fields(self, ci: ClassInfo) -> list[str]:
        return declarations_dc_fields(self, ci)

    def dc_factory(self, ci: ClassInfo, fl: str) -> None:
        return declarations_dc_factory(self, ci, fl)

    def is_prop(self, t: str, name: str) -> bool:
        return declarations_is_prop(self, t, name)

    def prop_store(self, o: Val, name: str, v: Val | None) -> None:
        return declarations_prop_store(self, o, name, v)

    def synth(self, ci: ClassInfo, name: str, ret: str, body: list[Node]) -> None:
        return declarations_synth(self, ci, name, ret, body)

    def dc_methods(self, ci: ClassInfo) -> None:
        return declarations_dc_methods(self, ci)

    def guess_varargs(self, init: FnInfo, args: list[Node], f: FnInfo) -> list[str]:
        return declarations_guess_varargs(self, init, args, f)

    def scan_fields(self, ci: ClassInfo, f: FnInfo, body: list[Node], known: dict[str, bool]) -> None:
        return declarations_scan_fields(self, ci, f, body, known)

    def guess_args(self, init: FnInfo, args: list[Node], f: FnInfo) -> list[str]:
        return declarations_guess_args(self, init, args, f)

    def guess(self, e: Node, f: FnInfo) -> str:
        return declarations_guess(self, e, f)

    def guess_iter(self, a: Node, f: FnInfo) -> str:
        return declarations_guess_iter(self, a, f)

    def field(self, o: Val, name: str, store: bool=False) -> Val:
        return declarations_field(self, o, name, store)

    def fgep(self, o: Val, i: int) -> str:
        return declarations_fgep(self, o, i)

    def fn_attr_read(self, o: Val, name: str) -> None:
        return declarations_fn_attr_read(self, o, name)

    def getfield(self, o: Val, p: Val, name: str) -> Val:
        return declarations_getfield(self, o, p, name)

    def setfield(self, o: Val, p: Val, name: str, v: Val) -> None:
        return declarations_setfield(self, o, p, name, v)

    def global_var(self, g: str, ty: str) -> None:
        return variables_global_var(self, g, ty)

    def is_global(self, name: str) -> bool:
        return variables_is_global(self, name)

    def unbound_local(self, name: str) -> bool:
        return variables_unbound_local(self, name)

    def read_ahead(self, name: str) -> None:
        return variables_read_ahead(self, name)

    def class_ahead(self, name: str) -> None:
        return variables_class_ahead(self, name)

    def no_type(self, name: str) -> None:
        return variables_no_type(self, name)

    def load_name(self, name: str) -> Val:
        return variables_load_name(self, name)

    def applies(self, st: Node, top: bool, loc: dict[str, bool]) -> bool:
        return variables_applies(self, st, top, loc)

    def scope_names(self) -> dict[str, bool]:
        return variables_scope_names(self)

    def decorate(self, n: Node) -> Val:
        return variables_decorate(self, n)

    def fn_names(self, t: str) -> list[str]:
        return variables_fn_names(self, t)

    def lib_fn(self, e: Node, qual: str) -> bool:
        return variables_lib_fn(self, e, qual)

    def wrap_names(self, v: Val, args: list[Node], vals: list[Val], what: str) -> None:
        return variables_wrap_names(self, v, args, vals, what)

    def deco_callee(self, x: Node, mod: str) -> Node:
        return variables_deco_callee(self, x, mod)

    def cellvars(self, f: FnInfo, body: list[Node]) -> list[str]:
        return variables_cellvars(self, f, body)

    def qualname(self, f: FnInfo) -> str:
        return variables_qualname(self, f)

    def closure(self, n: Node) -> Val:
        return variables_closure(self, n)

    def new_closure(self, n: Node, key: str) -> Closure:
        return variables_new_closure(self, n, key)

    def fn_value(self, name: str) -> Val:
        return variables_fn_value(self, name)

    def none_read(self, name: str) -> str:
        return variables_none_read(self, name)

    def none_type(self, name: str) -> str:
        return variables_none_type(self, name)

    def none_values(self, st: Node, name: str, out: list[Node]) -> None:
        return variables_none_values(self, st, name, out)

    def read(self, n: Node) -> Val:
        return variables_read(self, n)

    def modchk(self, n: Node) -> None:
        return variables_modchk(self, n)

    def imp_flag(self, x: str, glob: bool) -> str:
        return variables_imp_flag(self, x, glob)

    def foreign(self, name: str) -> bool:
        return variables_foreign(self, name)

    def unbound(self, name: str, imp: bool=False) -> str:
        return variables_unbound(self, name, imp)

    def qtype(self, name: str) -> str:
        return variables_qtype(self, name)

    def rtype(self, name: str) -> str:
        return variables_rtype(self, name)

    def globread(self, name: str) -> bool:
        return variables_globread(self, name)

    def where_def(self, name: str) -> str:
        return variables_where_def(self, name)

    def gtype(self, name: str) -> str:
        return variables_gtype(self, name)

    def ahead(self, name: str) -> str:
        return variables_ahead(self, name)

    def unpacked(self, st: Node, name: str) -> str:
        return variables_unpacked(self, st, name)

    def twin(self, x: str, y: str) -> None:
        return variables_twin(self, x, y)

    def twins(self, x: str) -> list[str]:
        return variables_twins(self, x)

    def calls_open(self, n: Node, seen: dict[str, bool]) -> bool:
        return variables_calls_open(self, n, seen)

    def modframe(self, mod: str, line: int) -> Frame:
        return variables_modframe(self, mod, line)

    def modtype(self, e: Node, mod: str) -> str:
        return variables_modtype(self, e, mod)

    def early(self, name: str) -> str:
        return variables_early(self, name)

    def unready(self, n: Node, mod: str, seen: dict[str, bool]) -> bool:
        return variables_unready(self, n, mod, seen)

    def decides(self, f: FnInfo, names: list[str]) -> bool:
        return variables_decides(self, f, names)

    def sets(self, f: FnInfo, names: list[str]) -> bool:
        return variables_sets(self, f, names)

    def first_binding(self, body: list[Node], name: str) -> Node | None:
        return variables_first_binding(self, body, name)

    def only_empties(self, body: list[Node], name: str) -> bool:
        return variables_only_empties(self, body, name)

    def live_blocks(self, st: Node) -> list[Node]:
        return variables_live_blocks(self, st)

    def static_now(self, n: Node) -> int:
        return variables_static_now(self, n)

    def static_whole(self, n: Node, line: int) -> int:
        return variables_static_whole(self, n, line)

    def none_ends(self) -> None:
        return variables_none_ends(self)

    def type_reads(self, n: Node) -> None:
        return variables_type_reads(self, n)

    def empty_of(self, e: Node) -> str:
        return variables_empty_of(self, e)

    def empty(self, kind: str, name: str) -> Val:
        return variables_empty(self, kind, name)

    def refine(self, name: str, t: str, glob: bool=False) -> None:
        return variables_refine(self, name, t, glob)

    def lookahead(self, name: str, ahead: bool=False) -> str:
        return variables_lookahead(self, name, ahead)

    def unfilled(self, name: str) -> bool:
        return variables_unfilled(self, name)

    def retval(self, e: Node, want: str) -> Val:
        return variables_retval(self, e, want)

    def adopt(self, t: str) -> None:
        return variables_adopt(self, t)

    def typed_empty(self, v: Val, want: str, f: FnInfo) -> Val:
        return variables_typed_empty(self, v, want, f)

    def fills(self, body: list[Node], name: str, found: list[Node]) -> bool:
        return variables_fills(self, body, name, found)

    def fill_calls(self, n: Node, name: str, found: list[Node]) -> None:
        return variables_fill_calls(self, n, name, found)

    def typed_now(self, e: Node, own: str='') -> bool:
        return variables_typed_now(self, e, own)

    def dry(self, e: Node, want: str='') -> str:
        return variables_dry(self, e, want)

    def fill(self, n: Node, m: str, args: list[Node], want: str='') -> Val:
        return variables_fill(self, n, m, args, want)

    def default_want(self, r: Node, m: str, args: list[Node], vt: str) -> str:
        return variables_default_want(self, r, m, args, vt)

    def new_global(self, name: str, t: str) -> None:
        return variables_new_global(self, name, t)

    def declare(self, name: str, t: str) -> None:
        return variables_declare(self, name, t)

    def store_name(self, name: str, v: Val, retype: bool = False) -> None:
        return variables_store_name(self, name, v, retype)

    def assigned_to(self, v: Val, t: str, name: str) -> str:
        return variables_assigned_to(self, v, t, name)

    def target_type(self, n: Node, base: bool=False) -> str:
        return variables_target_type(self, n, base)

    def assign(self, t: Node, v: Val) -> None:
        return variables_assign(self, t, v)

    def slice_target(self, t: Node, bnd: list[str], nosub: str) -> Val:
        return variables_slice_target(self, t, bnd, nosub)

    def slice_check(self, step: str) -> None:
        return variables_slice_check(self, step)

    def slice_store(self, o: Val, bnd: list[str], v: Val) -> None:
        return variables_slice_store(self, o, bnd, v)

    def slice_assign(self, t: Node, g: Node) -> None:
        return variables_slice_assign(self, t, g)
    def star_assign(self, t: Node, v: Val) -> None:
        return variables_star_assign(self, t, v)

    def walrus(self, n: Node, want: str) -> Val:
        return variables_walrus(self, n, want)
    def unpack_next(self, t: Node, it: Val) -> None:
        return variables_unpack_next(self, t, it)

    def list_slot(self, o: Val, i: str) -> str:
        return variables_list_slot(self, o, i)

    def enter(self, f: FnInfo, body: list[Node]) -> None:
        return functions_enter(self, f, body)

    def materialize(self, f: FnInfo) -> None:
        return functions_materialize(self, f)

    def function(self, f: FnInfo, body: list[Node]) -> None:
        return functions_function(self, f, body)

    def builtin_catch(self, b: str) -> str:
        return generators_builtin_catch(self, b)

    def gen_ann_ret(self, n: Node) -> list[str]:
        return generators_gen_ann_ret(self, n)

    def gen_begin(self, f: FnInfo) -> None:
        return generators_gen_begin(self, f)

    def gen_cleanup(self) -> int:
        return generators_gen_cleanup(self)

    def gen_unpack(self, t: Node, g: Val) -> None:
        return generators_gen_unpack(self, t, g)

    def gen_contains(self, x: Val, g: Val) -> Val:
        return generators_gen_contains(self, x, g)

    def gen_declare(self, f: FnInfo, d: Node) -> str:
        return generators_gen_declare(self, f, d)

    def gen_drop(self, h: Val) -> None:
        return generators_gen_drop(self, h)

    def gen_end(self, f: FnInfo) -> None:
        return generators_gen_end(self, f)

    def gen_enter(self) -> None:
        return generators_gen_enter(self)

    def hidden_loop(self, loop: Node, own: list[str], names: list[str]) -> None:
        return generators_hidden_loop(self, loop, own, names)

    def gen_list(self, v: Val, want: str) -> Val:
        return generators_gen_list(self, v, want)

    def gen_name(self, f: FnInfo) -> str:
        return generators_gen_name(self, f)

    def gen_next(self, h: Val, done: str) -> str:
        return generators_gen_next(self, h, done)

    def gen_none_end(self) -> None:
        return generators_gen_none_end(self)

    def none_null(self, t: str) -> bool:
        return generators_none_null(self, t)

    def gen_promise(self, h: Val) -> str:
        return generators_gen_promise(self, h)

    def gen_unhandle(self) -> None:
        return generators_gen_unhandle(self)


    def genexp_value(self, n: Node) -> Val:
        return generators_genexp_value(self, n)

    def gen_method(self, o: Val, m: str, args: list[Node]) -> Val:
        return generators_gen_method(self, o, m, args)

    def gen_next_value(self, g: Val, dflt: Val) -> Val:
        return generators_gen_next_value(self, g, dflt)

    def gen_ret(self, v: Val) -> None:
        return generators_gen_ret(self, v)

    def gen_return(self, n: Node) -> None:
        return generators_gen_return(self, n)

    def gen_stream(self, name: str, v: Val, args: list[Node], want: str, resultsoft: bool) -> Val:
        return generators_gen_stream(self, name, v, args, want, resultsoft)

    def gen_suspend(self, slot: str, k: int, sub: Val, thrown: str = "") -> None:
        return generators_gen_suspend(self, slot, k, sub, thrown)

    def yield_from_iter(self, what: str) -> None:
        return generators_yield_from_iter(self, what)

    def gen_type(self, y: str, s: str) -> str:
        return generators_gen_type(self, y, s)

    def yield_value(self, n: Node) -> Val:
        return generators_yield_value(self, n)

    def yield_from_proto(self, v: Val, t: str, y: str, callee: FnInfo | None) -> Val:
        return generators_yield_from_proto(self, v, t, y, callee)

    def gen_stop(self) -> None:
        return generators_gen_stop(self)

    def gen_raised(self, e: Val) -> None:
        return generators_gen_raised(self, e)

    def gen_close(self, h: Val) -> None:
        return generators_gen_close(self, h)

    def exc_mark(self) -> str:
        return generators_exc_mark(self)

    def pep479(self, e: Val) -> None:
        return generators_pep479(self, e)

    def exc_back(self, old: str) -> None:
        return generators_exc_back(self, old)

    def exc_operand(self, e: Node) -> Val:
        return generators_exc_operand(self, e)

    def gen_throw_into(self, h: Val, e: Val, done: str) -> str:
        return generators_gen_throw_into(self, h, e, done)

    def gen_throw(self, g: Val, args: list[Node]) -> Val:
        return generators_gen_throw(self, g, args)

    def gen_send(self, g: Val, args: list[Node]) -> Val:
        return generators_gen_send(self, g, args)

    def owned_gen(self, v: Val, it: Node) -> int:
        return generators_owned_gen(self, v, it)

    def owned_node(self, v: Val) -> Node:
        return generators_owned_node(self, v)

    def owned_loop(self, owned: list[Val], close: bool, tgt: Node, seqs: list[Val], mode: str, body: list[Node], start: str, hide: list[str], arg: IterArg | None, made: SeqStart | None) -> None:
        return generators_owned_loop(self, owned, close, tgt, seqs, mode, body, start, hide, arg, made)

    def yield_from(self, x: Node) -> Val:
        return generators_yield_from(self, x)

    def yield_stmt(self, n: Node) -> None:
        return generators_yield_stmt(self, n)

    def extern_args(self, x: Node, more: bool) -> list[str]:
        return functions_extern_args(self, x, more)

    def externtype(self, a: Node, t: str, what: str, f: FnInfo) -> str:
        return functions_externtype(self, a, t, what, f)

    def cextern(self, f: FnInfo) -> None:
        return lower_module_cextern(self, f)

    def pyext(self) -> list[str]:
        return lower_module_pyext(self)

    def untold(self, f: FnInfo, ts: list[str], how: str) -> None:
        return functions_untold(self, f, ts, how)

    def extern_decl(self, f: FnInfo) -> None:
        return lower_module_extern_decl(self, f)

    def lower_module(self) -> str:
        return lower_module_lower_module(self)

    def gen_module(self) -> list[str]:
        return lower_module_gen_module(self)

    def lower(self, fn: IFn) -> None:
        return lowering_lower(self, fn)

    def lower_ins(self, fn: IFn, i: Ins) -> None:
        return lowering_lower_ins(self, fn, i)

    def invoke(self, c: str, i: Ins) -> str:
        return lowering_invoke(self, c, i)

    def verify(self, fn: IFn, eh: bool) -> None:
        return ircheck_verify(self, fn, eh)

    def verify_gen(self, fn: IFn, b: Blk, i: Ins, j: int) -> None:
        return ircheck_verify_gen(self, fn, b, i, j)

    def nums(self, i: Ins) -> int:
        return ircheck_nums(self, i)

    def bad_ir(self, fn: IFn, b: Blk, what: str) -> None:
        return ircheck_bad_ir(self, fn, b, what)

    def effects(self) -> None:
        return ircheck_effects(self)

    def opfx(self, i: Ins, fa: dict[str, bool]) -> int:
        return ircheck_opfx(self, i, fa)

    def optimize(self, fn: IFn, on: dict[str, bool]) -> int:
        return optimizations_optimize(self, fn, on)

    def preds(self, fn: IFn) -> dict[str, list[int]]:
        return optimizations_preds(self, fn)

    def listget(self, fn: IFn) -> int:
        return optimizations_listget(self, fn)

    def dictfuse(self, fn: IFn) -> int:
        return optimizations_dictfuse(self, fn)

    def canon(self, vs: Values, v: str) -> str:
        return optimizations_canon(self, vs, v)

    def same(self, vs: Values, v: str, t: str) -> str:
        return optimizations_same(self, vs, v, t)

    def addr(self, vs: Values, a: str) -> str:
        return optimizations_addr(self, vs, a)

    def reaching(self, vs: Values, a: str, j: int, x: int) -> str:
        return optimizations_reaching(self, vs, a, j, x)

    def disjoint(self, vs: Values, a: str, b: str) -> bool:
        return optimizations_disjoint(self, vs, a, b)

    def eh_ir(self, fn: IFn) -> None:
        return lowering_eh_ir(self, fn)

    def subclass_problem(self, st: Node) -> str:
        return program_subclass_problem(self, st)

    def exc_base(self, b: Node) -> str:
        return program_exc_base(self, b)

    def inherit(self, ci: ClassInfo) -> None:
        return program_inherit(self, ci)

    def accessor(self, ci: ClassInfo, d: Node) -> str:
        return program_accessor(self, ci, d)

    def class_ref(self, m: Mod, s: str) -> str:
        return program_class_ref(self, m, s)

    def dc_options(self, ci: ClassInfo) -> None:
        return program_dc_options(self, ci)

    def derives(self, c: str, base: str) -> bool:
        return program_derives(self, c, base)

    def init_template(self, st: Node) -> bool:
        return program_init_template(self, st)

    def template_fix(self, cs: list[Node]) -> str:
        return program_template_fix(self, cs)

    def makes_tmpl(self, n: Node) -> bool:
        return program_makes_tmpl(self, n)

    def tmpl_ann(self, a: Node) -> bool:
        return program_tmpl_ann(self, a)

    def tmpl_of(self, c: str) -> str:
        return program_tmpl_of(self, c)

    def class_problem(self, m: Mod, st: Node, exc: bool) -> str:
        return program_class_problem(self, m, st, exc)

    def abstract_defs(self, body: list[Node]) -> list[Node]:
        return program_abstract_defs(self, body)

    def generic_aliases(self, body: list[Node]) -> None:
        return program_generic_aliases(self, body)

    def abstract_of(self, c: str) -> list[str]:
        return program_abstract_of(self, c)

    def abc_class(self, c: str) -> bool:
        return program_abc_class(self, c)

    def eager(self, e: str, why: str, does: str) -> None:
        return program_eager(self, e, why, does)

    def decorators(self, d: Node, decos: list[Node], local: dict[str, str]) -> str:
        return program_decorators(self, d, decos, local)

    def left_out(self, st: Node, why: str) -> None:
        return program_left_out(self, st, why)

    def class_effect(self, st: Node, why: str, runs: bool=True) -> bool:
        return program_class_effect(self, st, why, runs)

    def body_effect(self, body: list[Node], local: dict[str, str], why: str, does: str, runs: bool=True) -> bool:
        return program_body_effect(self, body, local, why, does, runs)

    def raisers(self, e: Node, local: dict[str, str], run: bool) -> bool:
        return program_raisers(self, e, local, run)

    def plain(self, e: Node, local: dict[str, str]) -> str:
        return program_plain(self, e, local)

    def body_names(self, c: Node) -> dict[str, bool]:
        return program_body_names(self, c)

    def hook(self, st: Node) -> None:
        return program_hook(self, st)

    def path_of(self, n: Node) -> str:
        return program_path_of(self, n)

    def objects(self, t: str, use: int) -> bool:
        return program_objects(self, t, use)

    def pure(self, q: str) -> bool:
        return program_pure(self, q)

    def effect(self, e: Node, local: dict[str, str], use: int) -> str:
        return program_effect(self, e, local, use)

    def partly(self, e: Node, use: int) -> str:
        return program_partly(self, e, use)

    def program(self, mods: list[Mod]) -> str:
        return program_program(self, mods)

    def flow_program(self, top: list[Node], mod: str, mfns: list[FnInfo], mcls: list[ClassInfo], first: bool) -> None:
        return flow_flow_program(self, top, mod, mfns, mcls, first)

    def flow_function(self, f: FnInfo, gl: dict[str, bool], safe: dict[str, bool], dels: dict[str, bool]) -> None:
        return flow_flow_function(self, f, gl, safe, dels)

    def fl_nested(self, fl: Flow, n: Node) -> None:
        return flow_fl_nested(self, fl, n)

    def fl_super(self, fl: Flow, m: str) -> bool:
        return flow_fl_super(self, fl, m)

    def flow_body(self, d: Node, caps: dict[str, bool]) -> None:
        return flow_flow_body(self, d, caps)

    def fl_fields(self, ci: ClassInfo) -> None:
        return flow_fl_fields(self, ci)

    def default_home(self, ci: ClassInfo, fl: str) -> ClassInfo:
        return flow_default_home(self, ci, fl)

    def fl_defaults(self, n: Node) -> list[Node]:
        return flow_fl_defaults(self, n)

    def scc(self, root: str, num: dict[str, int], low: dict[str, int], stack: list[str]) -> None:
        return flow_scc(self, root, num, low, stack)

    def user_call(self, n: Node) -> bool:
        return flow_user_call(self, n)

    def fl_stmts(self, fl: Flow, body: list[Node]) -> None:
        return flow_fl_stmts(self, fl, body)

    def fl_stmt(self, fl: Flow, n: Node) -> None:
        return flow_fl_stmt(self, fl, n)

    def fl_target(self, fl: Flow, t: Node) -> None:
        return flow_fl_target(self, fl, t)

    def fl_expr(self, fl: Flow, e: Node) -> None:
        return flow_fl_expr(self, fl, e)

    def stmts(self, body: list[Node]) -> None:
        return statements_stmts(self, body)

    def obj_helpers(self, c: str, which: list[int]) -> None:
        return statements_obj_helpers(self, c, which)

    def hash_helper(self, c: str) -> None:
        return statements_hash_helper(self, c)

    def dispatch(self, op: str) -> None:
        return lower_module_dispatch(self, op)

    def check_special(self, f: FnInfo) -> None:
        return statements_check_special(self, f)

    def scan_imports(self, body: list[Node]) -> None:
        return statements_scan_imports(self, body)

    def imported(self, name: str) -> str:
        return statements_imported(self, name)

    def check_import(self, a: Node) -> None:
        return statements_check_import(self, a)

    def hidden(self, name: str, v: Val) -> str:
        return statements_hidden(self, name, v)

    def dflt_fn(self, f: FnInfo) -> FnInfo:
        return statements_dflt_fn(self, f)

    def early_default(self, f: FnInfo, j: int) -> None:
        return statements_early_default(self, f, j)

    def class_default(self, ci: ClassInfo, fl: str) -> None:
        return statements_class_default(self, ci, fl)

    def hoist(self, f: FnInfo) -> None:
        return statements_hoist(self, f)

    def default_problem(self, e: Node, t: str) -> str:
        return statements_default_problem(self, e, t)

    def hoist_class(self, ci: ClassInfo) -> None:
        return statements_hoist_class(self, ci)

    def no_class_names(self, e: Node, bound: dict[str, bool], ci: ClassInfo) -> None:
        return statements_no_class_names(self, e, bound, ci)

    def unhashable(self, t: str) -> bool:
        return statements_unhashable(self, t)

    def while_(self, n: Node) -> None:
        return statements_while_(self, n)

    def loop(self, body: list[Node], lp: Loop) -> list[dict[str, str]]:
        return statements_loop(self, body, lp)

    def leave(self, depth: int) -> bool:
        return statements_leave(self, depth)

    def with_cm(self, m: Val, it: Node, body: list[Node]) -> None:
        return statements_with_cm(self, m, it, body)

    def cm_exits(self) -> bool:
        return statements_cm_exits(self)

    def suppress_item(self, e: Node) -> bool:
        return statements_suppress_item(self, e)

    def try_(self, n: Node) -> None:
        return exceptions_try_(self, n)

    def assert_fails(self, n: Node) -> None:
        return exceptions_assert_fails(self, n)

    def unnarrowed(self, bodies: list[list[Node]]) -> dict[str, str]:
        return exceptions_unnarrowed(self, bodies)

    def clause_or(self, t: Node) -> Node:
        return exceptions_clause_or(self, t)

    def catches(self, h: Node) -> str:
        return exceptions_catches(self, h)

    def exc_classes(self, t: Node) -> bool:
        return exceptions_exc_classes(self, t)

    def exc_isinst(self, v: Val, t: Node) -> Val:
        return exceptions_exc_isinst(self, v, t)

    def catch_set(self, t: Node) -> str:
        return exceptions_catch_set(self, t)

    def as_type(self, h: Node) -> str:
        return exceptions_as_type(self, h)

    def bind_as(self, name: str, e: Val, t: str) -> None:
        return exceptions_bind_as(self, name, e, t)

    def global_reader(self, name: str) -> str:
        return exceptions_global_reader(self, name)

    def unbinds(self, name: str) -> bool:
        return exceptions_unbinds(self, name)

    def unshadow(self) -> None:
        return exceptions_unshadow(self)

    def landing(self, l: str, slot: str, mark: Val) -> Val:
        return exceptions_landing(self, l, slot, mark)

    def exc_match(self, e: Val, names: str) -> str:
        return exceptions_exc_match(self, e, names)

    def unbind(self, name: str) -> None:
        return exceptions_unbind(self, name)

    def exc_args(self, e: Node) -> list[Node]:
        return exceptions_exc_args(self, e)

    def exc_kw(self, c: str, args: list[Node], what: str) -> None:
        return exceptions_exc_kw(self, c, args, what)

    def exc_vals(self, args: list[Node], name: str='') -> list[Val]:
        return exceptions_exc_vals(self, args, name)

    def exc_class(self, e: Node) -> str:
        return exceptions_exc_class(self, e)

    def cause(self, c: Node) -> Val:
        return exceptions_cause(self, c)

    def exc_value_of(self, e: Node, k: str) -> Val:
        return exceptions_exc_value_of(self, e, k)

    def raise_stmt(self, n: Node) -> None:
        return exceptions_raise_stmt(self, n)

    def os_error(self, name: str, vals: list[Val]) -> list[str]:
        return exceptions_os_error(self, name, vals)

    def unicode_error(self, name: str, vals: list[Val]) -> list[str]:
        return exceptions_unicode_error(self, name, vals)

    def exc_value(self, name: str, vals: list[Val]) -> Val:
        return exceptions_exc_value(self, name, vals)

    def exit_(self, vals: list[Val], sysx: bool) -> None:
        return exceptions_exit_(self, vals, sysx)

    def no_code(self) -> Val:
        return exceptions_no_code(self)

    def exit_value(self, vals: list[Val]) -> Val:
        return exceptions_exit_value(self, vals)

    def exc_object(self, c: str, args: list[Node]) -> Val:
        return exceptions_exc_object(self, c, args)

    def class_defaults(self, o: Val) -> None:
        return exceptions_class_defaults(self, o)

    def exc_keep(self, o: Val, vals: list[Val], coded: bool=True) -> None:
        return exceptions_exc_keep(self, o, vals, coded)

    def exc_of(self, v: Val) -> Val:
        return exceptions_exc_of(self, v)

    def exc_brepr(self, o: Val) -> Val:
        return exceptions_exc_brepr(self, o)

    def super_call(self, sc: Node, m: str, args: list[Node], based: bool=False, read: bool=False) -> Val:
        return exceptions_super_call(self, sc, m, args, based, read)

    def exc_helpers(self, c: str) -> None:
        return exceptions_exc_helpers(self, c)

    def throw(self, e: Val) -> None:
        return exceptions_throw(self, e)

    def raise_(self, name: str, msg: str, kind: str='') -> None:
        return exceptions_raise_(self, name, msg, kind)

    def stmt(self, n: Node) -> None:
        return statements_stmt(self, n)

    def nonemix(self, f: FnInfo, t: str) -> str:
        return statements_nonemix(self, f, t)

    def reopt(self, t: str) -> None:
        return statements_reopt(self, t)

    def del_name(self, n: Node) -> None:
        return statements_del_name(self, n)

    def augassign(self, n: Node) -> None:
        return statements_augassign(self, n)

    def owns(self, name: str) -> bool:
        return statements_owns(self, name)

    def str_append(self, t: Node, rhs: Node, shown: str) -> None:
        return statements_str_append(self, t, rhs, shown)

    def may_change(self, b0: Blk, x0: int, n0: int) -> bool:
        return statements_may_change(self, b0, x0, n0)

    def inplace(self, op: str, cur: Val, rhs: Node) -> Val:
        return statements_inplace(self, op, cur, rhs)

    def objlen(self, v: Val) -> Val:
        return statements_objlen(self, v)

    def none_operand(self, op: str, a: Val, b: Val) -> None:
        return statements_none_operand(self, op, a, b)

    def none_operands(self, op: str, a: Val, b: Val, shown: str, right: bool = True) -> None:
        return statements_none_operands(self, op, a, b, shown, right)

    def hide(self, names: list[str]) -> None:
        return statements_hide(self, names)

    def iterarg(self, arg: IterArg | None) -> None:
        return statements_iterarg(self, arg)

    def for_(self, n: Node, hide: list[str], arg: IterArg | None=None) -> None:
        return statements_for_(self, n, hide, arg)

    def iterable(self, v: Val, msg: str="TypeError: 'NoneType' object is not iterable") -> Val:
        return statements_iterable(self, v, msg)

    def ival(self, n: Node, none: str='') -> Val:
        return statements_ival(self, n, none)

    def range_args(self, args: list[Node]) -> list[str]:
        return statements_range_args(self, args)

    def for_range(self, tgt: Node, start: str, stop: str, step: str, body: list[Node], hide: list[str], arg: IterArg | None=None, check: bool=True) -> None:
        return statements_for_range(self, tgt, start, stop, step, body, hide, arg, check)

    def for_rrange(self, tgt: Node, vs: list[str], body: list[Node], hide: list[str], arg: IterArg | None=None) -> None:
        return statements_for_rrange(self, tgt, vs, body, hide, arg)

    def for_seq(self, tgt: Node, seqs: list[Val], mode: str, body: list[Node], start: str, hide: list[str], arg: IterArg | None=None, made: SeqStart | None=None) -> None:
        return statements_for_seq(self, tgt, seqs, mode, body, start, hide, arg, made)

    def seq_start(self, s: Val, mode: str, made: SeqStart) -> None:
        return statements_seq_start(self, s, mode, made)

    def seq_item(self, s: Val, j: str, mode: str) -> list[Val]:
        return statements_seq_item(self, s, j, mode)

    def stop_catch(self) -> StopCatch:
        return statements_stop_catch(self)

    def next_in(self, it: Val, c: StopCatch) -> Val:
        return statements_next_in(self, it, c)

    def stop_landing(self, c: StopCatch, stop: str) -> None:
        return statements_stop_landing(self, c, stop)

    def stop_classes(self) -> str:
        return statements_stop_classes(self)

    def drain(self, it: Val) -> Val:
        return statements_drain(self, it)

    def narrows(self, n: Node, truth: bool, out: dict[str, str]) -> None:
        return expressions_narrows(self, n, truth, out)

    def narrowable(self, name: str) -> bool:
        return expressions_narrowable(self, name)

    def narrow_by(self, test: Node, truth: bool) -> dict[str, str]:
        return expressions_narrow_by(self, test, truth)

    def forget_walrus(self, pre: dict[str, str], es: list[Node]) -> dict[str, str]:
        return expressions_forget_walrus(self, pre, es)

    def forget(self, body: list[Node], tgt: Node) -> dict[str, str]:
        return expressions_forget(self, body, tgt)

    def static(self, n: Node) -> int:
        return expressions_static(self, n)

    def static_len(self, n: Node) -> int:
        return expressions_static_len(self, n)

    def static_reads(self, n: Node) -> None:
        return expressions_static_reads(self, n)

    def knownobj(self, n: Node) -> bool:
        return expressions_knownobj(self, n)

    def has(self, t: str, a: str) -> int:
        return expressions_has(self, t, a)

    def static_type(self, n: Node, typed: bool=False) -> str:
        return expressions_static_type(self, n, typed)

    def isinst(self, t: str, c: Node) -> int:
        return expressions_isinst(self, t, c)

    def class_matches(self, c: str, t: Node) -> bool:
        return expressions_class_matches(self, c, t)

    def obj_isinst(self, v: Val, t: Node) -> Val:
        return expressions_obj_isinst(self, v, t)

    def isnone(self, t: str) -> int:
        return expressions_isnone(self, t)

    def isinst_reads(self, c: Node) -> None:
        return expressions_isinst_reads(self, c)

    def puretype(self, c: Node, u: bool) -> bool:
        return expressions_puretype(self, c, u)

    def cond(self, n: Node) -> str:
        return expressions_cond(self, n)

    def truth(self, v: Val) -> str:
        return expressions_truth(self, v)

    def expr(self, n: Node, want: str, returnctx: bool = False, resultsoft: bool = False) -> Val:
        return expressions_expr(self, n, want, returnctx, resultsoft)

    def list_hint_type(self, a: str, b: str) -> str:
        return expressions_list_hint_type(self, a, b)

    def class_attr(self, cn: Node, a: str) -> Val:
        return expressions_class_attr(self, cn, a)

    def cvar_stores(self, ns: list[Node]) -> None:
        return expressions_cvar_stores(self, ns)

    def cvar(self, cn: Node, a: str) -> ClassInfo:
        return expressions_cvar(self, cn, a)

    def class_store(self, ci: ClassInfo, a: str, v: Val) -> None:
        return expressions_class_store(self, ci, a, v)

    def no_class_attr(self, c: str, a: str) -> None:
        return expressions_no_class_attr(self, c, a)

    def class_ready(self, cn: Node) -> ClassInfo:
        return expressions_class_ready(self, cn)

    def class_call(self, cn: Node, m: str, args: list[Node], want: str, resultsoft: bool = False) -> Val:
        return expressions_class_call(self, cn, m, args, want, resultsoft)

    def cls_bound(self, f: FnInfo, c: str, obj: bool) -> None:
        return expressions_cls_bound(self, f, c, obj)

    def percent(self, fmt: str, rhs: Node) -> Val:
        return expressions_percent(self, fmt, rhs)

    def percent_opt(self, fmt: str, v: Val) -> Val:
        return expressions_percent_opt(self, fmt, v)

    def pformat(self, fmt: str, items: list[Val], rtnone: bool) -> Val:
        return expressions_pformat(self, fmt, items, rtnone)

    def nonefmt(self, t: str) -> str:
        return expressions_nonefmt(self, t)

    def fmt_error(self, msg: str) -> Val:
        return expressions_fmt_error(self, msg)

    def str_format(self, fmt: str, m: str, args: list[Node]) -> Val:
        return expressions_str_format(self, fmt, m, args)

    def format_of(self, f: Node) -> Node:
        return expressions_format_of(self, f)

    def const_str(self, o: Node) -> Node:
        return expressions_const_str(self, o)

    def format_args(self, fa: FmtArgs, args: list[Node]) -> bool:
        return expressions_format_args(self, fa, args)

    def format_kw(self, fa: FmtArgs, name: str, v: Val) -> bool:
        return expressions_format_kw(self, fa, name, v)

    def format_dup(self, fa: FmtArgs, name: str) -> None:
        return expressions_format_dup(self, fa, name)

    def format_merge(self, fa: FmtArgs) -> None:
        return expressions_format_merge(self, fa)

    def fmt_raise(self, kind: str, msg: str) -> Val:
        return expressions_fmt_raise(self, kind, msg)

    def str_fields(self, s: str, depth: int, fa: FmtArgs) -> Val:
        return expressions_str_fields(self, s, depth, fa)

    def str_field(self, name: str, conv: str, spec: str, expand: bool, depth: int, fa: FmtArgs) -> Val:
        return expressions_str_field(self, name, conv, spec, expand, depth, fa)

    def format_arg(self, first: str, idx: int, fa: FmtArgs) -> Val:
        return expressions_format_arg(self, first, idx, fa)

    def cat(self, a: Val, b: Val) -> Val:
        return expressions_cat(self, a, b)

    def concat(self, parts: list[Val]) -> Val:
        return expressions_concat(self, parts)

    def conversion(self, v: Val, flags: str, width: str, prec: str, t: str) -> Val:
        return expressions_conversion(self, v, flags, width, prec, t)

    def format_(self, v: Val, spec: Node) -> Val:
        return expressions_format_(self, v, spec)

    def optbound(self, v: Val) -> str:
        return expressions_optbound(self, v)

    def slice_bound(self, x: Node, fold: bool=False) -> str:
        return expressions_slice_bound(self, x, fold)

    def slice_step(self, x: Node, fold: bool=False) -> str:
        return expressions_slice_step(self, x, fold)

    def slice_tuple(self, o: Val, bnd: list[str], step: str) -> Val:
        return expressions_slice_tuple(self, o, bnd, step)

    def optint(self, v: Val, none: str) -> str:
        return expressions_optint(self, v, none)

    def numkey(self, v: Val, t: str) -> list[str]:
        return expressions_numkey(self, v, t)

    def tuple_(self, vals: list[Val]) -> Val:
        return expressions_tuple_(self, vals)

    def dict_merge(self, n: Node, want: str) -> Val:
        return expressions_dict_merge(self, n, want)

    def unroll(self, g: Node, every: bool = False) -> list[Node] | None:
        return expressions_unroll(self, g, every)

    def pick(self, o: Val, tests: list[Val], exc: str, msg: str, what: str, want: str, dflt: Val | None = None) -> Val:
        return expressions_pick(self, o, tests, exc, msg, what, want, dflt)

    def iter_static(self, n: Node) -> str:
        return expressions_iter_static(self, n)

    def stack_tuple(self, vals: list[Val]) -> Val:
        return expressions_stack_tuple(self, vals)

    def stack_ok(self, f: FnInfo) -> bool:
        return expressions_stack_ok(self, f)

    def keep_stack(self, n: Node) -> None:
        return expressions_keep_stack(self, n)

    def stack_target(self, t: Node, out: dict[str, bool]) -> None:
        return expressions_stack_target(self, t, out)

    def stack_uses(self, n: Node, out: dict[str, bool]) -> None:
        return expressions_stack_uses(self, n, out)

    def lookup_key(self, n: Node) -> bool:
        return expressions_lookup_key(self, n)

    def probe_type(self, n: Node) -> str:
        return expressions_probe_type(self, n)

    def tget(self, v: Val, i: int) -> Val:
        return expressions_tget(self, v, i)

    def tstore(self, v: Val, index: int, slot: str) -> None:
        expressions_tstore(self, v, index, slot)

    def index(self, n: Node, want: str = "") -> Val:
        return expressions_index(self, n, want)

    def subscript(self, n: Node, o: Val, want: str = "") -> Val:
        return expressions_subscript(self, n, o, want)

    def list_read(self, o: Val, i: Val) -> Val:
        return expressions_list_read(self, o, i)

    def argtype(self, t: str, m: str, j: int, missing: str) -> str:
        return expressions_argtype(self, t, m, j, missing)

    def protocol(self, o: Val, m: str, args: list[Val]) -> Val:
        return expressions_protocol(self, o, m, args)

    def obj_iter(self, v: Val, none: str, missing: str, name: str = "__iter__") -> Val:
        return expressions_obj_iter(self, v, none, missing, name)

    def obj_iterator(self, v: Val, none: str, missing: str, name: str = "__iter__") -> Val:
        return expressions_obj_iterator(self, v, none, missing, name)

    def is_iterator(self, t: str) -> bool:
        return expressions_is_iterator(self, t)

    def next_type(self, t: str) -> str:
        return expressions_next_type(self, t)

    def iter_ret(self, e: Node) -> Val:
        return expressions_iter_ret(self, e)

    def listcomp(self, n: Node, want: str, mode: str='', into: str='', arg: IterArg | None=None, kind: str='list', resultsoft: bool = False) -> Val:
        return expressions_listcomp(self, n, want, mode, into, arg, kind, resultsoft)

    def ifexp(self, n: Node, want: str, resultsoft: bool = False) -> Val:
        return expressions_ifexp(self, n, want, resultsoft)

    def boolop(self, n: Node, ascond: bool, want: str, resultsoft: bool = False) -> Val:
        return expressions_boolop(self, n, ascond, want, resultsoft)

    def unary(self, n: Node) -> Val:
        return expressions_unary(self, n)

    def dunder(self, op: str, a: Val, b: Val, shown: str='') -> Val:
        return expressions_dunder(self, op, a, b, shown)

    def ntop(self, op: str, a: Val, b: Val, shown: str) -> Val:
        return expressions_ntop(self, op, a, b, shown)

    def ntup(self, v: Val, known: bool=False) -> Val:
        return expressions_ntup(self, v, known)

    def cmp_method(self, t: str, m: str, other: str) -> str:
        return expressions_cmp_method(self, t, m, other)

    def exc_kinds(self, t: str) -> list[str]:
        return expressions_exc_kinds(self, t)

    def cmp_kinds(self, t: str) -> list[str]:
        return expressions_cmp_kinds(self, t)

    def cmp_pick(self, op: str, at: str, bt: str) -> list[str]:
        return expressions_cmp_pick(self, op, at, bt)

    def inherit_cmp(self, op: str, a: Val, b: Val, phase: int=0) -> Val:
        return expressions_inherit_cmp(self, op, a, b, phase)

    def inherit_contains(self, op: str, a: Val, b: Val) -> Val:
        return expressions_inherit_contains(self, op, a, b)

    def member_item(self, item: Val, a: Val, found: str, ph: Ins) -> None:
        return expressions_member_item(self, item, a, found, ph)

    def iter_in(self, op: str, a: Val, it: Val) -> Val:
        return expressions_iter_in(self, op, a, it)

    def concrete_cmp(self, op: str, a: Val, b: Val) -> Val:
        return expressions_concrete_cmp(self, op, a, b)

    def isnull(self, v: Val) -> str:
        return expressions_isnull(self, v)

    def richcmp(self, op: str, a: Val, b: Val) -> Val:
        return expressions_richcmp(self, op, a, b)

    def eqcall(self, f: FnInfo, iseq: bool, a: Val, b: Val) -> Val:
        return expressions_eqcall(self, f, iseq, a, b)

    def arith(self, op: str, a: Val, b: Val, shown: str='') -> Val:
        return expressions_arith(self, op, a, b, shown)

    def compare(self, n: Node) -> Val:
        return expressions_compare(self, n)

    def exc_id(self, v: Val) -> Val:
        return expressions_exc_id(self, v)

    def exc_eq(self, t: str, what: str='') -> None:
        return expressions_exc_eq(self, t, what)

    def cmp2(self, op: str, a: Val, b: Val) -> Val:
        return expressions_cmp2(self, op, a, b)

    def titem_eq(self, item: Val, a: Val, hit: str, ph: Ins | None, value: str) -> bool:
        return expressions_titem_eq(self, item, a, hit, ph, value)

    def tuple_order(self, op: str, a: Val, b: Val) -> Val:
        return expressions_tuple_order(self, op, a, b)

    def optcmp(self, op: str, a: Val, b: Val) -> Val:
        return expressions_optcmp(self, op, a, b)

    def comparable(self, t: str, u: str) -> bool:
        return expressions_comparable(self, t, u)

    def numeric_comparable(self, t: str, u: str) -> bool:
        return expressions_numeric_comparable(self, t, u)

    def foreign_eq(self, a: Val, b: Val) -> Val:
        return expressions_foreign_eq(self, a, b)

    def call(self, n: Node, want: str, resultsoft: bool = False, typeargs: str = "") -> Val:
        return calls_call(self, n, want, resultsoft, typeargs)

    def star_call(self, n: Node, want: str, resultsoft: bool = False, typeargs: str = "") -> Val:
        return calls_star_call(self, n, want, resultsoft, typeargs)

    def static_callee(self, f: Node) -> bool:
        return calls_static_callee(self, f)

    def star_who(self, f: Node) -> str:
        return calls_star_who(self, f)

    def print_star(self, n: Node, args: list[Node]) -> Val:
        return calls_print_star(self, n, args)

    def not_callable(self, name: str, t: str) -> None:
        return calls_not_callable(self, name, t)

    def obj_call(self, o: Val, args: list[Node], want: str, resultsoft: bool = False) -> Val:
        return calls_obj_call(self, o, args, want, resultsoft)

    def cached_wrapper(self, t: str) -> bool:
        return calls_cached_wrapper(self, t)

    def call_cache(self, o: Val, args: list[Node], want: str, resultsoft: bool = False) -> Val:
        return calls_call_cache(self, o, args, want, resultsoft)

    def to_callable(self, v: Val, t: str) -> Val:
        return calls_to_callable(self, v, t)

    def adapter(self, ft: str, t: str) -> str:
        return calls_adapter(self, ft, t)

    def callable_pat(self, a: Node) -> str:
        return calls_callable_pat(self, a)

    def pat_arg(self, v: Val, a: Node) -> Val:
        return calls_pat_arg(self, v, a)

    def adapter_ret(self, ft: str, ps: list[str]) -> str:
        return calls_adapter_ret(self, ft, ps)

    def call_callable(self, o: Val, args: list[Node]) -> Val:
        return calls_call_callable(self, o, args)

    def call_value(self, v: Val, args: list[Node], want: str, resultsoft: bool = False) -> Val:
        return calls_call_value(self, v, args, want, resultsoft)

    def bound(self, s: str) -> bool:
        return calls_bound(self, s)

    def open_call(self, n: Node) -> bool:
        return calls_open_call(self, n)

    def close_temp(self, n: Node, v: Val) -> None:
        return calls_close_temp(self, n, v)

    def open_(self, args: list[Node]) -> Val:
        return calls_open_(self, args)

    def method(self, o: Val, m: str, args: list[Node], want: str='', resultsoft: bool = False) -> Val:
        return calls_method(self, o, m, args, want, resultsoft)

    def unbound_call(self, tn: str, m: str, args: list[Node]) -> Val:
        return calls_unbound_call(self, tn, m, args)

    def kw_record(self, names: list[str], vals: list[Val]) -> Val:
        return calls_kw_record(self, names, vals)

    def kw_method(self, o: Val, m: str, args: list[Node]) -> Val:
        return calls_kw_method(self, o, m, args)

    def kw_repr(self, v: Val) -> Val:
        return calls_kw_repr(self, v)

    def kw_list(self, v: Val) -> Val:
        return calls_kw_list(self, v)

    def kw_tuple(self, v: Val) -> Val:
        return calls_kw_tuple(self, v)

    def kw_dict(self, v: Val) -> Val:
        return calls_kw_dict(self, v)

    def method_value(self, o: Val, name: str) -> Val:
        return calls_method_value(self, o, name)

    def replace(self, o: Val, args: list[Node]) -> Val:
        return calls_replace(self, o, args)

    def nt_new(self, c: str, vals: list[Val], want: str) -> Val:
        return calls_nt_new(self, c, vals, want)

    def nt_make(self, c: str, args: list[Node], want: str) -> Val:
        return calls_nt_make(self, c, args, want)

    def asdict(self, o: Val, args: list[Node]) -> Val:
        return calls_asdict(self, o, args)

    def dc_replace(self, args: list[Node]) -> Val:
        return calls_dc_replace(self, args)

    def new_obj(self, c: str) -> Val:
        return calls_new_obj(self, c)

    def pcoerce(self, v: Val, t: str, f: FnInfo, j: int) -> Val:
        return calls_pcoerce(self, v, t, f, j)

    def call_fn(self, f: FnInfo, pre: list[Val], args: list[Node], want: str='', none: str='', cache: Val | None=None, direct: bool=False, resultsoft: bool = False, typeargs: str = "") -> Val:
        return calls_call_fn(self, f, pre, args, want, none, cache, direct, resultsoft, typeargs)

    def virtual_call(self, f: FnInfo, pre: list[Val], args: list[Node], want: str, none: str, resultsoft: bool = False) -> Val:
        return calls_virtual_call(self, f, pre, args, want, none, resultsoft)

    def fname(self, f: FnInfo) -> str:
        return calls_fname(self, f)

    def arity(self, f: FnInfo, npre: int, args: list[Node]) -> None:
        return calls_arity(self, f, npre, args)

    def kw_type(self, f: FnInfo, name: str) -> str:
        return calls_kw_type(self, f, name)

    def dispatches(self, f: FnInfo, p: str) -> bool:
        return calls_dispatches(self, f, p)

    def tests(self, ns: list[Node], p: str) -> bool:
        return calls_tests(self, ns, p)

    def specialize(self, c: str, ts: list[str], given: dict[str, str], named: bool, lits: dict[str, Node]) -> str:
        return templates_specialize(self, c, ts, given, named, lits)

    def getattr_name(self, n: Node) -> str:
        return calls_getattr_name(self, n)

    def literal_class(self, c: str) -> bool:
        return templates_literal_class(self, c)

    def literal_args(self, f: FnInfo, args: list[Node]) -> dict[str, Node]:
        return templates_literal_args(self, f, args)

    def lit_context(self) -> bool:
        return templates_lit_context(self)

    def const_of(self, n: Node, env: dict[str, Node], live: bool) -> Node | None:
        return templates_const_of(self, n, env, live)

    def const_fields(self, s: ClassInfo, init: FnInfo) -> None:
        return templates_const_fields(self, s, init)

    def names_tv(self, a: Node, tvs: list[str]) -> bool:
        return templates_names_tv(self, a, tvs)

    def bind(self, c: str, ts: list[str], given: dict[str, str]) -> dict[str, str]:
        return templates_bind(self, c, ts, given)

    def want_tvars(self, c: str, want: str) -> dict[str, str]:
        return templates_want_tvars(self, c, want)

    def constructor_unions(self, c: str, ts: list[str]) -> list[str]:
        return templates_constructor_unions(self, c, ts)

    def want_params(self, c: str, want: str) -> list[str]:
        return templates_want_params(self, c, want)

    def generic_hint(self, e: Node, t: str) -> str:
        return templates_generic_hint(self, e, t)

    def generic_ann(self, c: str, a: Node) -> str:
        return templates_generic_ann(self, c, a)

    def named_params(self, c: str, init: Node) -> list[str]:
        return templates_named_params(self, c, init)

    def named_param(self, a: Node) -> str:
        return templates_named_param(self, a)

    def match(self, a: Node, t: str, tv: dict[str, str], tvs: list[str]) -> str:
        return templates_match(self, a, t, tv, tvs)

    def match_items(self, xs: list[Node], ts: list[str], tv: dict[str, str], tvs: list[str]) -> str:
        return templates_match_items(self, xs, ts, tv, tvs)

    def fn_sig(self, t: str) -> list[str]:
        return templates_fn_sig(self, t)

    def instance(self, f: FnInfo, ts: list[str], nnp: list[str], want: str = "", resultsoft: bool = False) -> FnInfo:
        return templates_instance(self, f, ts, nnp, want, resultsoft)

    def dotted(self, n: Node) -> str:
        return builtins_dotted(self, n)

    def modattr(self, path: str) -> Val:
        return builtins_modattr(self, path)

    def builtin(self, name: str, args: list[Node], want: str, resultsoft: bool = False) -> Val:
        return builtins_builtin(self, name, args, want, resultsoft)

    def vnode(self, v: Val) -> Node:
        return builtins_vnode(self, v)

    def key_check(self, key: Val, of: str) -> None:
        return builtins_key_check(self, key, of)

    def key_none(self, key: Val, et: str, use: str, of: str) -> str:
        return builtins_key_none(self, key, et, use, of)

    def key_free(self, t: str, use: str) -> bool:
        return builtins_key_free(self, t, use)

    def key_none_join(self, r: Val, lnone: str, xs: Val, vals: list[Val], name: str) -> Val:
        return builtins_key_none_join(self, r, lnone, xs, vals, name)

    def call_key(self, key: Val, x: Val) -> Val:
        return builtins_call_key(self, key, x)

    def callable_type(self, t: str) -> int:
        return builtins_callable_type(self, t)

    def callable_guard(self, st: Node, f: FnInfo) -> str:
        return statements_callable_guard(self, st, f)

    def keys_of(self, xs: Val, key: Val) -> Val:
        return builtins_keys_of(self, xs, key)

    def key_sort(self, xs: Val, key: Val, rev: str, taken: bool) -> None:
        return builtins_key_sort(self, xs, key, rev, taken)

    def key_minmax(self, xs: Val, key: Val, name: str) -> Val:
        return builtins_key_minmax(self, xs, key, name)

    def key_minmax2(self, vals: list[Val], key: Val, name: str) -> Val:
        return builtins_key_minmax2(self, vals, key, name)

    def key_minmax_next(self, o: Val, key: Val, name: str) -> Val:
        return builtins_key_minmax_next(self, o, key, name)

    def iter_object(self, t: str) -> bool:
        return builtins_iter_object(self, t)

    def anyall(self, v: Val, name: str) -> Val:
        return builtins_anyall(self, v, name)

    def stream_start(self, name: str, args: list[Node]) -> str:
        return builtins_stream_start(self, name, args)

    def reduce(self, name: str, args: list[Node], stt: str) -> Val:
        return builtins_reduce(self, name, args, stt)

    def reduce_item(self, r: Reduce, e: Node) -> None:
        return builtins_reduce_item(self, r, e)

    def iterator_call(self, n: Node) -> bool:
        return builtins_iterator_call(self, n)

    def is_mapcall(self, n: Node) -> bool:
        return builtins_is_mapcall(self, n)

    def mapgen(self, n: Node) -> Node:
        return builtins_mapgen(self, n)

    def consume(self, n: Node, want: str, arg: IterArg | None=None, resultsoft: bool = False) -> Val:
        return builtins_consume(self, n, want, arg, resultsoft)

    def as_list(self, v: Val, name: str) -> Val:
        return builtins_as_list(self, v, name)

    def reverse_arg(self, n: Node, name: str) -> str:
        return builtins_reverse_arg(self, n, name)

    def bytes_method(self, o: Val, m: str, args: list[Node]) -> Val:
        return builtins_bytes_method(self, o, m, args)

    def struct_call(self, name: str, args: list[Node], want: str) -> Val | None:
        return structs_struct_call(self, name, args, want)

    def struct_format(self, a: Node) -> Node | None:
        return structs_struct_format(self, a)

    def struct_helper(self, f: str, args: list[Node]) -> Node:
        return structs_struct_helper(self, f, args)

    def struct_nodes(self, sf: StructFmt, bn: Node, base: Node | None) -> list[Node]:
        return structs_struct_nodes(self, sf, bn, base)

    def struct_pack(self, sf: StructFmt, args: list[Node]) -> Val:
        return structs_struct_pack(self, sf, args)

    def bytes_(self, args: list[Node]) -> Val:
        return builtins_bytes_(self, args)

    def reverse_val(self, r: Val, name: str) -> str:
        return builtins_reverse_val(self, r, name)

    def parse_expr(self, text: str) -> Node:
        return builtins_parse_expr(self, text)

    def print_(self, args: list[Node]) -> Val:
        return builtins_print_(self, args)

    def next_(self, args: list[Node], want: str) -> Val:
        return builtins_next_(self, args, want)

    def iter_(self, args: list[Node]) -> Val:
        return builtins_iter_(self, args)

    def iter_obj(self, name: str, vals: list[Val]) -> Val:
        return builtins_iter_obj(self, name, vals)

    def walk(self, name: str, args: list[Node]) -> Val:
        return builtins_walk(self, name, args)

    def range_prim(self, name: str, args: list[Node]) -> Val:
        return builtins_range_prim(self, name, args)

    def range_fields(self, v: Val) -> list[str]:
        return builtins_range_fields(self, v)

    def pwrite(self, fd: str, fv: str, s: str, fo: Val) -> None:
        return builtins_pwrite(self, fd, fv, s, fo)

    def bmethod(self, o: Val, m: str, args: list[Node], first: bool=False) -> Val:
        return builtins_bmethod(self, o, m, args, first)

    def update(self, o: Val, args: list[Node]) -> Val:
        return builtins_update(self, o, args)

    def tmethod(self, o: Val, m: str, args: list[Node]) -> Val:
        return builtins_tmethod(self, o, m, args)

    def dict_pairs(self, v: Val, want: str, found: str = "") -> Val:
        return builtins_dict_pairs(self, v, want, found)

    def isclose(self, args: list[Node]) -> Val:
        return builtins_isclose(self, args)

    def prod_item(self, s: Val, item: Val) -> Val:
        return builtins_prod_item(self, s, item)

    def prod_seq(self, xs: Val, s: Val) -> Val:
        return builtins_prod_seq(self, xs, s)

    def set_display(self, n: Node, want: str, folded: bool, returnctx: bool = False, resultsoft: bool = False) -> Val:
        return containers_set_display(self, n, want, folded, returnctx, resultsoft)

    def star_items(self, x: Node) -> Val:
        return containers_star_items(self, x)

    def star_display(self, n: Node, want: str) -> Val:
        return containers_star_display(self, n, want)

    def iter_elem(self, t: str) -> str:
        return containers_iter_elem(self, t)

    def siter(self, n: Node, et: str, what: str, resultsoft: bool = False) -> Val:
        return containers_siter(self, n, et, what, resultsoft)

    def sitems(self, v: Val, et: str, what: str) -> Val:
        return containers_sitems(self, v, et, what)

    def supdate(self, s: str, v: Val, et: str) -> None:
        return containers_supdate(self, s, v, et)

    def sdiscard(self, ov: str, v: Val, et: str) -> None:
        return containers_sdiscard(self, ov, v, et)

    def sargs(self, o: Val, m: str, args: list[Node]) -> list[SetArg]:
        return containers_sargs(self, o, m, args)

    def stake(self, o: Val, m: str, x: SetArg) -> Val:
        return containers_stake(self, o, m, x)

    def sgen(self, o: Val, m: str, g: Node, arg: IterArg | None) -> Val:
        return containers_sgen(self, o, m, g, arg)

    def keys_list(self, v: Val) -> Val:
        return containers_keys_list(self, v)

    def set_new(self, name: str, args: list[Node], want: str, resultsoft: bool = False) -> Val:
        return containers_set_new(self, name, args, want, resultsoft)

    def setop(self, op: str, a: Val, b: Val) -> Val:
        return containers_setop(self, op, a, b)

    def smethod(self, o: Val, m: str, args: list[Node]) -> Val:
        return containers_smethod(self, o, m, args)

    def fromkeys(self, args: list[Node], want: str, resultsoft: bool = False) -> Val:
        return containers_fromkeys(self, args, want, resultsoft)

    def affix_any(self, tup: Val, m: str, av: list[str], base: str = "str") -> Val:
        return containers_affix_any(self, tup, m, av, base)

    def optdefault(self, d: Val, t: str) -> str:
        return containers_optdefault(self, d, t)

    def key_kind(self, kt: str) -> str:
        return containers_key_kind(self, kt)

    def key_class(self, t: str) -> bool:
        return containers_key_class(self, t)

    def key_items(self, t: str) -> bool:
        return containers_key_items(self, t)

    def key_problem(self, t: str) -> str:
        return containers_key_problem(self, t)

    def elem_problem(self, t: str) -> str:
        return containers_elem_problem(self, t)

    def hash_kind(self, c: str) -> str:
        return containers_hash_kind(self, c)

    def hash_classes(self, t: str) -> list[ClassInfo]:
        return containers_hash_classes(self, t)

    def hash_desc(self, t: str) -> str:
        return containers_hash_desc(self, t)

    def key_fx(self, kt: str) -> str:
        return containers_key_fx(self, kt)

    def key_repr(self, t: str) -> bool:
        return containers_key_repr(self, t)

    def obj_hash(self, v: Val) -> Val:
        return containers_obj_hash(self, v)

    def hash_value(self, v: Val) -> Val:
        return containers_hash_value(self, v)

    def hashable(self, t: str) -> bool:
        return containers_hashable(self, t)

    def dkey(self, k: Val, kt: str) -> Val:
        return containers_dkey(self, k, kt)

    def bool_find(self, d: str, k: Val, key: str) -> str:
        return containers_bool_find(self, d, k, key)

    def store_key(self, k: Val, kt: str) -> Val:
        return containers_store_key(self, k, kt)

    def store_elem(self, k: Val, et: str) -> Val:
        return containers_store_elem(self, k, et)

    def nonekey(self, k: Val, none: str, fn: str, av: list[str], x: str) -> str:
        return containers_nonekey(self, k, none, fn, av, x)

    def keyed(self, k: Val, av: list[str]) -> list[str]:
        return containers_keyed(self, k, av)

    def none_arg(self, m: str, k: int) -> str:
        return containers_none_arg(self, m, k)

    def to_str(self, v: Val) -> Val:
        return containers_to_str(self, v)

    def obj_str(self, v: Val, m: str) -> Val:
        return containers_obj_str(self, v, m)

    def repr(self, v: Val) -> Val:
        return containers_repr(self, v)

    def ueq_type(self, t: str) -> bool:
        return unions_ueq_type(self, t)

    def scalar_union(self, t: str) -> bool:
        return unions_scalar_union(self, t)

    def value_union(self, t: str) -> bool:
        return unions_value_union(self, t)

    def uop(self, v: Val, op: str) -> Val:
        return unions_uop(self, v, op)

    def uequal(self, op: str, a: Val, b: Val) -> Val:
        return unions_uequal(self, op, a, b)

    def unumeric(self, op: str, a: Val, b: Val, shown: str, unary: bool) -> Val:
        return union_arithmetic_unumeric(self, op, a, b, shown, unary)

    def unumeric_case(self, op: str, a: Val, b: Val, shown: str, unary: bool) -> Val:
        return union_arithmetic_unumeric_case(self, op, a, b, shown, unary)

    def reference_union(self, t: str) -> bool:
        return unions_reference_union(self, t)

    def umethod(self, o: Val, m: str, args: list[Node]) -> Val:
        return unions_umethod(self, o, m, args)

    def uboxes(self, a: str, b: str) -> bool:
        return unions_uboxes(self, a, b)

    def umember_problem(self, t: str) -> str:
        return unions_umember_problem(self, t)

    def union_type(self, ts: list[str]) -> str:
        return unions_union_type(self, ts)

    def utag(self, t: str) -> int:
        return unions_utag(self, t)

    def ubox(self, v: Val, m: str) -> str:
        return unions_ubox(self, v, m)

    def uget(self, u: Val, m: str) -> Val:
        return unions_uget(self, u, m)

    def utest(self, u: Val, ms: list[str], may_none: bool) -> str:
        return unions_utest(self, u, ms, may_none)

    def to_union(self, v: Val, t: str, what: str) -> Val:
        return unions_to_union(self, v, t, what)

    def narrow_val(self, v: Val, nt: str) -> Val:
        return unions_narrow_val(self, v, nt)

    def unarrowed(self, v: Val) -> str:
        return unions_unarrowed(self, v)

    def uisinst(self, v: Val, c: Node) -> str:
        return unions_uisinst(self, v, c)

    def now_type(self, name: str) -> str:
        return unions_now_type(self, name)

    def isinst_narrow(self, t: str, c: Node, truth: bool) -> str:
        return unions_isinst_narrow(self, t, c, truth)

    def holds(self, t: str, vt: str) -> str:
        return unions_holds(self, t, vt)
