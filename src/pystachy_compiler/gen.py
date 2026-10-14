"""Gen component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.builtins import (
    gen_anyall as builtins_anyall,
    gen_as_list as builtins_as_list,
    gen_bmethod as builtins_bmethod,
    gen_builtin as builtins_builtin,
    gen_call_key as builtins_call_key,
    gen_consume as builtins_consume,
    gen_dotted as builtins_dotted,
    gen_is_mapcall as builtins_is_mapcall,
    gen_iterator_call as builtins_iterator_call,
    gen_key_check as builtins_key_check,
    gen_key_minmax as builtins_key_minmax,
    gen_key_minmax2 as builtins_key_minmax2,
    gen_key_sort as builtins_key_sort,
    gen_keys_of as builtins_keys_of,
    gen_mapgen as builtins_mapgen,
    gen_modattr as builtins_modattr,
    gen_parse_expr as builtins_parse_expr,
    gen_print_ as builtins_print_,
    gen_pwrite as builtins_pwrite,
    gen_reduce as builtins_reduce,
    gen_reduce_item as builtins_reduce_item,
    gen_reverse_arg as builtins_reverse_arg,
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
    gen_bound as calls_bound,
    gen_cached_wrapper as calls_cached_wrapper,
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
    gen_star_call as calls_star_call,
    gen_star_who as calls_star_who,
    gen_static_callee as calls_static_callee,
    gen_tests as calls_tests,
    gen_to_callable as calls_to_callable,
    gen_unbound_call as calls_unbound_call,
)
from src.pystachy_compiler.containers import (
    gen_affix_any as containers_affix_any,
    gen_bool_find as containers_bool_find,
    gen_dkey as containers_dkey,
    gen_fromkeys as containers_fromkeys,
    gen_iter_elem as containers_iter_elem,
    gen_key_kind as containers_key_kind,
    gen_keyed as containers_keyed,
    gen_keys_list as containers_keys_list,
    gen_none_arg as containers_none_arg,
    gen_nonekey as containers_nonekey,
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
    gen_store_elem as containers_store_elem,
    gen_store_key as containers_store_key,
    gen_supdate as containers_supdate,
    gen_to_str as containers_to_str,
)
from src.pystachy_compiler.conversions import (
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
    gen_ann as declarations_ann,
    gen_ann_base as declarations_ann_base,
    gen_ann_items as declarations_ann_items,
    gen_ann_problem as declarations_ann_problem,
    gen_boxto as declarations_boxto,
    gen_boxwider as declarations_boxwider,
    gen_class_tvars as declarations_class_tvars,
    gen_ctype as declarations_ctype,
    gen_dc_methods as declarations_dc_methods,
    gen_declare_fields as declarations_declare_fields,
    gen_declare_fn as declarations_declare_fn,
    gen_exc_attr as declarations_exc_attr,
    gen_fgep as declarations_fgep,
    gen_field as declarations_field,
    gen_frozen as declarations_frozen,
    gen_generic_base as declarations_generic_base,
    gen_getfield as declarations_getfield,
    gen_guess as declarations_guess,
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
    gen_opt as declarations_opt,
    gen_optional as declarations_optional,
    gen_path_union as declarations_path_union,
    gen_pathlike as declarations_pathlike,
    gen_scan_fields as declarations_scan_fields,
    gen_self_type as declarations_self_type,
    gen_setfield as declarations_setfield,
    gen_shadowed as declarations_shadowed,
    gen_stub as declarations_stub,
    gen_subst as declarations_subst,
    gen_synth as declarations_synth,
    gen_tvar as declarations_tvar,
    gen_typeof as declarations_typeof,
    gen_typevar_def as declarations_typevar_def,
    gen_typevar_in as declarations_typevar_in,
    gen_typing_attr as declarations_typing_attr,
    gen_typing_forms as declarations_typing_forms,
    gen_typing_name as declarations_typing_name,
    gen_typing_ref as declarations_typing_ref,
    gen_union_members as declarations_union_members,
    gen_unpack_ann as declarations_unpack_ann,
    gen_vtype as declarations_vtype,
    gen_widens as declarations_widens,
    gen_wider as declarations_wider,
)
from src.pystachy_compiler.emission import (
    gen_add as emission_add,
    gen_alloca as emission_alloca,
    gen_boxes as emission_boxes,
    gen_br as emission_br,
    gen_cbr as emission_cbr,
    gen_checked as emission_checked,
    gen_convert_at as emission_convert_at,
    gen_convert_in as emission_convert_in,
    gen_converts as emission_converts,
    gen_deref as emission_deref,
    gen_emit as emission_emit,
    gen_err as emission_err,
    gen_guard as emission_guard,
    gen_hole as emission_hole,
    gen_incoming as emission_incoming,
    gen_ins as emission_ins,
    gen_iop as emission_iop,
    gen_jump as emission_jump,
    gen_label as emission_label,
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
    gen_cmp_method as expressions_cmp_method,
    gen_comparable as expressions_comparable,
    gen_compare as expressions_compare,
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
    gen_foreign_eq as expressions_foreign_eq,
    gen_forget as expressions_forget,
    gen_format_ as expressions_format_,
    gen_has as expressions_has,
    gen_ifexp as expressions_ifexp,
    gen_index as expressions_index,
    gen_isinst as expressions_isinst,
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
    gen_optbound as expressions_optbound,
    gen_optcmp as expressions_optcmp,
    gen_optint as expressions_optint,
    gen_percent as expressions_percent,
    gen_percent_opt as expressions_percent_opt,
    gen_pformat as expressions_pformat,
    gen_probe_type as expressions_probe_type,
    gen_protocol as expressions_protocol,
    gen_puretype as expressions_puretype,
    gen_richcmp as expressions_richcmp,
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
    gen_truth as expressions_truth,
    gen_tuple_ as expressions_tuple_,
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
    gen_fl_stmt as flow_fl_stmt,
    gen_fl_stmts as flow_fl_stmts,
    gen_fl_target as flow_fl_target,
    gen_flow_body as flow_flow_body,
    gen_flow_function as flow_flow_function,
    gen_flow_program as flow_flow_program,
    gen_scc as flow_scc,
    gen_user_call as flow_user_call,
)
from src.pystachy_compiler.functions import (
    gen_cextern as functions_cextern,
    gen_enter as functions_enter,
    gen_extern_args as functions_extern_args,
    gen_externtype as functions_externtype,
    gen_function as functions_function,
    gen_materialize as functions_materialize,
    gen_pyext as functions_pyext,
    gen_untold as functions_untold,
)
from src.pystachy_compiler.ir import (
    Blk,
    ClassInfo,
    Closure,
    Exit,
    FnInfo,
    Frame,
    IFn,
    Ins,
    IterArg,
    Loop,
    Reduce,
    SeqStart,
    SetArg,
    Val,
    Values,
)
from src.pystachy_compiler.ircheck import (
    gen_bad_ir as ircheck_bad_ir,
    gen_effects as ircheck_effects,
    gen_nums as ircheck_nums,
    gen_opfx as ircheck_opfx,
    gen_verify as ircheck_verify,
)
from src.pystachy_compiler.lowering import (
    gen_eh_ir as lowering_eh_ir,
    gen_invoke as lowering_invoke,
    gen_lower as lowering_lower,
    gen_lower_ins as lowering_lower_ins,
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
    gen_class_problem as program_class_problem,
    gen_decorators as program_decorators,
    gen_derives as program_derives,
    gen_eager as program_eager,
    gen_effect as program_effect,
    gen_exc_base as program_exc_base,
    gen_hook as program_hook,
    gen_inherit as program_inherit,
    gen_init_template as program_init_template,
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
    gen_check_import as statements_check_import,
    gen_check_special as statements_check_special,
    gen_class_default as statements_class_default,
    gen_default_problem as statements_default_problem,
    gen_del_name as statements_del_name,
    gen_dflt_fn as statements_dflt_fn,
    gen_dispatch as statements_dispatch,
    gen_early_default as statements_early_default,
    gen_for_ as statements_for_,
    gen_for_range as statements_for_range,
    gen_for_rrange as statements_for_rrange,
    gen_for_seq as statements_for_seq,
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
    gen_loop as statements_loop,
    gen_may_change as statements_may_change,
    gen_no_class_names as statements_no_class_names,
    gen_none_operand as statements_none_operand,
    gen_none_operands as statements_none_operands,
    gen_nonemix as statements_nonemix,
    gen_obj_helpers as statements_obj_helpers,
    gen_objlen as statements_objlen,
    gen_range_args as statements_range_args,
    gen_reopt as statements_reopt,
    gen_scan_imports as statements_scan_imports,
    gen_seq_start as statements_seq_start,
    gen_stmt as statements_stmt,
    gen_stmts as statements_stmts,
    gen_unhashable as statements_unhashable,
    gen_while_ as statements_while_,
)
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.templates import (
    gen_bind as templates_bind,
    gen_fn_sig as templates_fn_sig,
    gen_instance as templates_instance,
    gen_match as templates_match,
    gen_match_items as templates_match_items,
    gen_names_tv as templates_names_tv,
    gen_specialize as templates_specialize,
)
from src.pystachy_compiler.utils import RtFn, fxmask
from src.pystachy_compiler.variables import (
    gen_adopt as variables_adopt,
    gen_ahead as variables_ahead,
    gen_applies as variables_applies,
    gen_assign as variables_assign,
    gen_assigned_to as variables_assigned_to,
    gen_calls_open as variables_calls_open,
    gen_cellvars as variables_cellvars,
    gen_class_ahead as variables_class_ahead,
    gen_closure as variables_closure,
    gen_decides as variables_decides,
    gen_declare as variables_declare,
    gen_deco_callee as variables_deco_callee,
    gen_decorate as variables_decorate,
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
    gen_where_def as variables_where_def,
)


class Gen:
    def __init__(self):
        self.classes: dict[str, ClassInfo] = {}
        self.tmpl: dict[str, bool] = {}  # the class templates (an __init__ parameter without an annotation)
        self.compiling = False  # every declaration is made: code is being compiled (see guess)
        self.specing: dict[str, str] = {}  # the specializations being made, by template and argument types
        self.specdone: dict[str, str] = {}  # and those made, which the same call gets again
        self.selfcls = ""  # the class whose method or fields are being declared: what typing.Self is
        self.funcs: dict[str, FnInfo] = {}
        self.aliases: dict[str, str] = {}
        self.imports: dict[str, str] = {}
        self.fglobals: dict[str, bool] = {}
        self.mvars: dict[str, bool] = {}  # module-level variables, also those functions assign
        self.gtypes: dict[str, str] = {}
        self.globs: list[str] = []
        self.gcroots: list[str] = []
        self.consts: list[str] = []
        self.strs: dict[str, str] = {}
        self.strvals: list[str] = []  # the text of each @s.N
        self.vnodes: list[Val] = []  # the values of "val" nodes, which the compiler makes (vnode)
        # the runtime functions declared, by RUNTIME key, in the order of their first use (which
        # the program's declare lines keep)
        self.rtfns: dict[str, RtFn] = {}
        self.opfxs: dict[str, int] = {}  # the effects of each op of IROPS but raw, rt, call and init
        for op in IROPS:
            self.opfxs[op] = fxmask(IROPS[op].replace("T", "").replace("*", ""))
        self.out: list[str] = []
        self.fns: list[IFn] = []  # the functions compiled, in the order they were completed
        self.fll: dict[str, int] = {}  # and their positions there by symbol, once the program is built
        self.ltype: dict[str, str] = {}
        self.lreg: dict[str, str] = {}
        self.gdecl: dict[str, bool] = {}
        self.assigned: dict[str, bool] = {}
        self.compvars: dict[str, int] = {}
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
        self.lenient = False
        self.uflags: dict[str, bool] = {}
        self.lflag: dict[str, str] = {}
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
        # optional locals (and parameters) known not to be None here, as mypy narrows them: a read
        # of one has the type it holds (see narrows)
        self.narrowed: dict[str, bool] = {}
        self.nonecmp = False  # the read being compiled is compared with None (see none_type)
        self.anyopt = False  # a local of an optional type exists: narrows has something to look for
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
        self.intat: dict[str, int] = {}  # the line of each constant's own binding (including from-imports)
        self.falseflags: dict[str, bool] = {}  # each module's TYPE_CHECKING that is a constant False (false_flag())
        # an imported module's globals (and defs and classes) that other code may find unbound:
        # not assigned on every path through its module code, or before an import that may run
        # code calling back into the module
        self.late: dict[str, bool] = {}
        self.lib = False  # declaring an imported module's function: what it cannot compile is an error only where it is called
        self.ext = ""  # pystachy ext: the name of the CPython extension module the program becomes
        self.csyms: dict[str, str] = {}  # @ffi.extern: each C symbol's declare (one signature per program)
        self.csymline: dict[str, int] = {}  # and the line that declared it
        self.extvars: dict[str, int] = {}  # pystachy ext: the main module's variables, and the line that binds each
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
        self.elsekids: list[Node] = []  # the body of a for/while ... else loop being compiled
        self.elsebrk = ""  # and the label after its else block
        self.brks: list[list[dict[str, bool]]] = []  # for each loop being compiled, what narrowed holds at its breaks
        self.elsebrks: list[dict[str, bool]] = []  # those of the last loop with an else block
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
        self.qused: dict[str, bool] = {}
        self.inited: dict[str, bool] = {}  # the modules whose top-level code is compiled
        self.guessed: dict[str, str] = {}  # by function: why such a container is list[int] or dict[int, int] there, for a type error
        self.nts: dict[str, bool] = {}  # the typing.NamedTuple classes: a dataclass whose fields cannot be assigned (see nt_class)
        # "C.x": class attribute x of plain class C, which the program assigns through the class
        # (C.x = v, cls.x += 1): a global that objects read until they assign x (see cvar_stores)
        self.cvars: dict[str, bool] = {}
        self.typevars: list[str] = []  # module globals bound to typing.TypeVar(...) or TypeVarTuple(...), which only annotations may name
        self.tvtuples: dict[str, bool] = {}  # those bound to a TypeVarTuple, which an annotation unpacks (*Ts)
        # the generic classes (class C(Generic[T, *Ts])): their type variables, which the arguments
        # of the call that makes an object bind (see bind)
        self.tparams: dict[str, list[str]] = {}

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

    def emit(self, s: str) -> None:
        return emission_emit(self, s)

    def add(self, i: Ins) -> None:
        return emission_add(self, i)

    def put(self, i: Ins, k: int) -> None:
        return emission_put(self, i, k)

    def ins(self, s: str) -> str:
        return emission_ins(self, s)

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

    def rt(self, name: str, ret: str, args: list[str]) -> str:
        return emission_rt(self, name, ret, args)

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

    def class_tvars(self, cls: str) -> list[str]:
        return declarations_class_tvars(self, cls)

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

    def declare_fn(self, d: Node, cls: str, inherited: bool=False) -> FnInfo:
        return declarations_declare_fn(self, d, cls, inherited)

    def iter_ann(self, n: Node) -> str:
        return declarations_iter_ann(self, n)

    def iter_item(self, n: Node) -> Node:
        return declarations_iter_item(self, n)

    def exc_attr(self, ci: ClassInfo, name: str) -> None:
        return declarations_exc_attr(self, ci, name)

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

    def frozen(self, t: str, name: str) -> None:
        return declarations_frozen(self, t, name)

    def synth(self, ci: ClassInfo, name: str, ret: str, body: list[Node]) -> None:
        return declarations_synth(self, ci, name, ret, body)

    def dc_methods(self, ci: ClassInfo) -> None:
        return declarations_dc_methods(self, ci)

    def scan_fields(self, ci: ClassInfo, f: FnInfo, body: list[Node]) -> None:
        return declarations_scan_fields(self, ci, f, body)

    def guess_args(self, init: FnInfo, args: list[Node], f: FnInfo) -> list[str]:
        return declarations_guess_args(self, init, args, f)

    def guess(self, e: Node, f: FnInfo) -> str:
        return declarations_guess(self, e, f)

    def field(self, o: Val, name: str, store: bool=False) -> Val:
        return declarations_field(self, o, name, store)

    def fgep(self, o: Val, i: int) -> str:
        return declarations_fgep(self, o, i)

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

    def none_values(self, body: list[Node], name: str, out: list[Node]) -> None:
        return variables_none_values(self, body, name, out)

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

    def dry(self, e: Node) -> str:
        return variables_dry(self, e)

    def fill(self, n: Node, m: str, args: list[Node], want: str='') -> Val:
        return variables_fill(self, n, m, args, want)

    def default_want(self, r: Node, m: str, args: list[Node], vt: str) -> str:
        return variables_default_want(self, r, m, args, vt)

    def new_global(self, name: str, t: str) -> None:
        return variables_new_global(self, name, t)

    def declare(self, name: str, t: str) -> None:
        return variables_declare(self, name, t)

    def store_name(self, name: str, v: Val) -> None:
        return variables_store_name(self, name, v)

    def assigned_to(self, v: Val, t: str, name: str) -> str:
        return variables_assigned_to(self, v, t, name)

    def target_type(self, n: Node, base: bool=False) -> str:
        return variables_target_type(self, n, base)

    def assign(self, t: Node, v: Val) -> None:
        return variables_assign(self, t, v)

    def enter(self, f: FnInfo, body: list[Node]) -> None:
        return functions_enter(self, f, body)

    def materialize(self, f: FnInfo) -> None:
        return functions_materialize(self, f)

    def function(self, f: FnInfo, body: list[Node]) -> None:
        return functions_function(self, f, body)

    def extern_args(self, x: Node, more: bool) -> list[str]:
        return functions_extern_args(self, x, more)

    def externtype(self, a: Node, t: str, what: str, f: FnInfo) -> str:
        return functions_externtype(self, a, t, what, f)

    def cextern(self, f: FnInfo) -> None:
        return functions_cextern(self, f)

    def pyext(self) -> list[str]:
        return functions_pyext(self)

    def untold(self, f: FnInfo, ts: list[str], how: str) -> None:
        return functions_untold(self, f, ts, how)

    def lower(self, fn: IFn) -> None:
        return lowering_lower(self, fn)

    def lower_ins(self, fn: IFn, i: Ins) -> None:
        return lowering_lower_ins(self, fn, i)

    def invoke(self, c: str, i: Ins) -> str:
        return lowering_invoke(self, c, i)

    def verify(self, fn: IFn, eh: bool) -> None:
        return ircheck_verify(self, fn, eh)

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

    def derives(self, c: str, base: str) -> bool:
        return program_derives(self, c, base)

    def init_template(self, st: Node) -> bool:
        return program_init_template(self, st)

    def makes_tmpl(self, n: Node) -> bool:
        return program_makes_tmpl(self, n)

    def tmpl_ann(self, a: Node) -> bool:
        return program_tmpl_ann(self, a)

    def tmpl_of(self, c: str) -> str:
        return program_tmpl_of(self, c)

    def class_problem(self, m: Mod, st: Node, exc: bool) -> str:
        return program_class_problem(self, m, st, exc)

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

    def obj_helpers(self, c: str) -> None:
        return statements_obj_helpers(self, c)

    def dispatch(self, op: str) -> None:
        return statements_dispatch(self, op)

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

    def loop(self, body: list[Node], lp: Loop) -> list[dict[str, bool]]:
        return statements_loop(self, body, lp)

    def leave(self, depth: int) -> bool:
        return statements_leave(self, depth)

    def try_(self, n: Node) -> None:
        return exceptions_try_(self, n)

    def assert_fails(self, n: Node) -> None:
        return exceptions_assert_fails(self, n)

    def unnarrowed(self, bodies: list[list[Node]]) -> dict[str, bool]:
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

    def cause(self, c: Node) -> None:
        return exceptions_cause(self, c)

    def exc_value_of(self, e: Node, k: str) -> Val:
        return exceptions_exc_value_of(self, e, k)

    def raise_stmt(self, n: Node) -> None:
        return exceptions_raise_stmt(self, n)

    def os_error(self, name: str, vals: list[Val]) -> list[str]:
        return exceptions_os_error(self, name, vals)

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

    def super_call(self, sc: Node, m: str, args: list[Node], based: bool=False) -> Val:
        return exceptions_super_call(self, sc, m, args, based)

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

    def may_change(self, b0: Blk, x0: int, n0: int) -> bool:
        return statements_may_change(self, b0, x0, n0)

    def inplace(self, op: str, cur: Val, rhs: Node) -> Val:
        return statements_inplace(self, op, cur, rhs)

    def objlen(self, v: Val) -> Val:
        return statements_objlen(self, v)

    def none_operand(self, op: str, a: Val, b: Val) -> None:
        return statements_none_operand(self, op, a, b)

    def none_operands(self, op: str, a: Val, b: Val, shown: str) -> None:
        return statements_none_operands(self, op, a, b, shown)

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

    def for_range(self, tgt: Node, start: str, stop: str, step: str, body: list[Node], hide: list[str], arg: IterArg | None=None) -> None:
        return statements_for_range(self, tgt, start, stop, step, body, hide, arg)

    def for_rrange(self, tgt: Node, vs: list[str], body: list[Node], hide: list[str], arg: IterArg | None=None) -> None:
        return statements_for_rrange(self, tgt, vs, body, hide, arg)

    def for_seq(self, tgt: Node, seqs: list[Val], mode: str, body: list[Node], start: str, hide: list[str], arg: IterArg | None=None, made: SeqStart | None=None) -> None:
        return statements_for_seq(self, tgt, seqs, mode, body, start, hide, arg, made)

    def seq_start(self, s: Val, mode: str, made: SeqStart) -> None:
        return statements_seq_start(self, s, mode, made)

    def narrows(self, n: Node, truth: bool, out: list[str]) -> None:
        return expressions_narrows(self, n, truth, out)

    def narrowable(self, name: str) -> bool:
        return expressions_narrowable(self, name)

    def narrow_by(self, test: Node, truth: bool) -> dict[str, bool]:
        return expressions_narrow_by(self, test, truth)

    def forget(self, body: list[Node], tgt: Node) -> dict[str, bool]:
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

    def expr(self, n: Node, want: str) -> Val:
        return expressions_expr(self, n, want)

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

    def class_call(self, cn: Node, m: str, args: list[Node], want: str) -> Val:
        return expressions_class_call(self, cn, m, args, want)

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

    def optint(self, v: Val, none: str) -> str:
        return expressions_optint(self, v, none)

    def numkey(self, v: Val, t: str) -> list[str]:
        return expressions_numkey(self, v, t)

    def tuple_(self, vals: list[Val]) -> Val:
        return expressions_tuple_(self, vals)

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

    def index(self, n: Node) -> Val:
        return expressions_index(self, n)

    def subscript(self, n: Node, o: Val) -> Val:
        return expressions_subscript(self, n, o)

    def list_read(self, o: Val, i: Val) -> Val:
        return expressions_list_read(self, o, i)

    def argtype(self, t: str, m: str, j: int, missing: str) -> str:
        return expressions_argtype(self, t, m, j, missing)

    def protocol(self, o: Val, m: str, args: list[Val]) -> Val:
        return expressions_protocol(self, o, m, args)

    def obj_iter(self, v: Val, none: str, missing: str) -> Val:
        return expressions_obj_iter(self, v, none, missing)

    def iter_ret(self, e: Node) -> Val:
        return expressions_iter_ret(self, e)

    def listcomp(self, n: Node, want: str, mode: str='', into: str='', arg: IterArg | None=None, kind: str='list') -> Val:
        return expressions_listcomp(self, n, want, mode, into, arg, kind)

    def ifexp(self, n: Node, want: str) -> Val:
        return expressions_ifexp(self, n, want)

    def boolop(self, n: Node, ascond: bool, want: str) -> Val:
        return expressions_boolop(self, n, ascond, want)

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

    def tuple_order(self, op: str, a: Val, b: Val) -> Val:
        return expressions_tuple_order(self, op, a, b)

    def optcmp(self, op: str, a: Val, b: Val) -> Val:
        return expressions_optcmp(self, op, a, b)

    def comparable(self, t: str, u: str) -> bool:
        return expressions_comparable(self, t, u)

    def foreign_eq(self, a: Val, b: Val) -> Val:
        return expressions_foreign_eq(self, a, b)

    def call(self, n: Node, want: str) -> Val:
        return calls_call(self, n, want)

    def star_call(self, n: Node, want: str) -> Val:
        return calls_star_call(self, n, want)

    def static_callee(self, f: Node) -> bool:
        return calls_static_callee(self, f)

    def star_who(self, f: Node) -> str:
        return calls_star_who(self, f)

    def print_star(self, n: Node, args: list[Node]) -> Val:
        return calls_print_star(self, n, args)

    def not_callable(self, name: str, t: str) -> None:
        return calls_not_callable(self, name, t)

    def obj_call(self, o: Val, args: list[Node], want: str) -> Val:
        return calls_obj_call(self, o, args, want)

    def cached_wrapper(self, t: str) -> bool:
        return calls_cached_wrapper(self, t)

    def call_cache(self, o: Val, args: list[Node], want: str) -> Val:
        return calls_call_cache(self, o, args, want)

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

    def call_value(self, v: Val, args: list[Node], want: str) -> Val:
        return calls_call_value(self, v, args, want)

    def bound(self, s: str) -> bool:
        return calls_bound(self, s)

    def open_call(self, n: Node) -> bool:
        return calls_open_call(self, n)

    def close_temp(self, n: Node, v: Val) -> None:
        return calls_close_temp(self, n, v)

    def open_(self, args: list[Node]) -> Val:
        return calls_open_(self, args)

    def method(self, o: Val, m: str, args: list[Node]) -> Val:
        return calls_method(self, o, m, args)

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

    def asdict(self, o: Val, args: list[Node]) -> Val:
        return calls_asdict(self, o, args)

    def new_obj(self, c: str) -> Val:
        return calls_new_obj(self, c)

    def pcoerce(self, v: Val, t: str, f: FnInfo, j: int) -> Val:
        return calls_pcoerce(self, v, t, f, j)

    def call_fn(self, f: FnInfo, pre: list[Val], args: list[Node], want: str='', none: str='', cache: Val | None=None) -> Val:
        return calls_call_fn(self, f, pre, args, want, none, cache)

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

    def specialize(self, c: str, ts: list[str]) -> str:
        return templates_specialize(self, c, ts)

    def names_tv(self, a: Node, tvs: list[str]) -> bool:
        return templates_names_tv(self, a, tvs)

    def bind(self, c: str, ts: list[str]) -> dict[str, str]:
        return templates_bind(self, c, ts)

    def match(self, a: Node, t: str, tv: dict[str, str], tvs: list[str]) -> str:
        return templates_match(self, a, t, tv, tvs)

    def match_items(self, xs: list[Node], ts: list[str], tv: dict[str, str], tvs: list[str]) -> str:
        return templates_match_items(self, xs, ts, tv, tvs)

    def fn_sig(self, t: str) -> list[str]:
        return templates_fn_sig(self, t)

    def instance(self, f: FnInfo, ts: list[str], nnp: list[str]) -> FnInfo:
        return templates_instance(self, f, ts, nnp)

    def dotted(self, n: Node) -> str:
        return builtins_dotted(self, n)

    def modattr(self, path: str) -> Val:
        return builtins_modattr(self, path)

    def builtin(self, name: str, args: list[Node], want: str) -> Val:
        return builtins_builtin(self, name, args, want)

    def vnode(self, v: Val) -> Node:
        return builtins_vnode(self, v)

    def key_check(self, key: Val, of: str) -> None:
        return builtins_key_check(self, key, of)

    def call_key(self, key: Val, x: Val) -> Val:
        return builtins_call_key(self, key, x)

    def keys_of(self, xs: Val, key: Val) -> Val:
        return builtins_keys_of(self, xs, key)

    def key_sort(self, xs: Val, key: Val, rev: str, taken: bool) -> None:
        return builtins_key_sort(self, xs, key, rev, taken)

    def key_minmax(self, xs: Val, key: Val, name: str) -> Val:
        return builtins_key_minmax(self, xs, key, name)

    def key_minmax2(self, vals: list[Val], key: Val, name: str) -> Val:
        return builtins_key_minmax2(self, vals, key, name)

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

    def consume(self, n: Node, want: str, arg: IterArg | None=None) -> Val:
        return builtins_consume(self, n, want, arg)

    def as_list(self, v: Val, name: str) -> Val:
        return builtins_as_list(self, v, name)

    def reverse_arg(self, n: Node, name: str) -> str:
        return builtins_reverse_arg(self, n, name)

    def reverse_val(self, r: Val, name: str) -> str:
        return builtins_reverse_val(self, r, name)

    def parse_expr(self, text: str) -> Node:
        return builtins_parse_expr(self, text)

    def print_(self, args: list[Node]) -> Val:
        return builtins_print_(self, args)

    def pwrite(self, fd: str, fv: str, s: str, fo: Val) -> None:
        return builtins_pwrite(self, fd, fv, s, fo)

    def bmethod(self, o: Val, m: str, args: list[Node], first: bool=False) -> Val:
        return builtins_bmethod(self, o, m, args, first)

    def update(self, o: Val, args: list[Node]) -> Val:
        return builtins_update(self, o, args)

    def set_display(self, n: Node, want: str, folded: bool) -> Val:
        return containers_set_display(self, n, want, folded)

    def iter_elem(self, t: str) -> str:
        return containers_iter_elem(self, t)

    def siter(self, n: Node, et: str, what: str) -> Val:
        return containers_siter(self, n, et, what)

    def sitems(self, v: Val, et: str, what: str) -> Val:
        return containers_sitems(self, v, et, what)

    def supdate(self, s: str, v: Val) -> None:
        return containers_supdate(self, s, v)

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

    def set_new(self, name: str, args: list[Node], want: str) -> Val:
        return containers_set_new(self, name, args, want)

    def setop(self, op: str, a: Val, b: Val) -> Val:
        return containers_setop(self, op, a, b)

    def smethod(self, o: Val, m: str, args: list[Node]) -> Val:
        return containers_smethod(self, o, m, args)

    def fromkeys(self, args: list[Node], want: str) -> Val:
        return containers_fromkeys(self, args, want)

    def affix_any(self, tup: Val, m: str, av: list[str]) -> Val:
        return containers_affix_any(self, tup, m, av)

    def optdefault(self, d: Val, t: str) -> str:
        return containers_optdefault(self, d, t)

    def key_kind(self, kt: str) -> str:
        return containers_key_kind(self, kt)

    def dkey(self, k: Val, kt: str) -> Val:
        return containers_dkey(self, k, kt)

    def bool_find(self, d: str, k: Val, key: str) -> str:
        return containers_bool_find(self, d, k, key)

    def store_key(self, k: Val, kt: str) -> Val:
        return containers_store_key(self, k, kt)

    def store_elem(self, k: Val, et: str) -> Val:
        return containers_store_elem(self, k, et)

    def nonekey(self, k: Val, none: str, fn: str, av: list[str]) -> str:
        return containers_nonekey(self, k, none, fn, av)

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
