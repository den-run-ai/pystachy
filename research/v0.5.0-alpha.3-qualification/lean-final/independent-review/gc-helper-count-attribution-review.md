# Independent GC helper denominator review

Sixteen fixtures lose 102 counted GC obligations because 18 previously emitted internal mappingproxy reflected-union helpers are omitted. Each old helper symbol occurs exactly once in the full retained LLVM module, at its internal definition; there is no call or address-taken reference. Each is absent from the candidate typed function inventory and LLVM module. The complete mappingproxy library file is byte-identical across the two sources.

The review rehashed all raw snapshots and compact/extracted inventories, matched the complete typed helper functions to the raw snapshot array, and located every recorded GC origin in the exact old typed operations. Full LLVM helper bodies, signatures, origin operations and source hashes are retained in JSON. Each str/int dictionary helper contributes three counted obligations; the remaining sixteen helper instances contribute six each.

| Fixture | Omitted helpers | Fewer GC obligations |
| --- | ---: | ---: |
| lib_types_mappingproxy_eq_other.py | 1 | 3 |
| port_tomli_w_ini2toml.py | 1 | 6 |
| port_tomli_w_tables.py | 1 | 6 |
| port_tomli_w_values.py | 1 | 6 |
| lib_enum.py | 2 | 12 |
| lib_enum_mixin.py | 1 | 6 |
| lib_tomllib.py | 1 | 6 |
| lib_tomllib_boundary.py | 1 | 6 |
| lib_tomllib_dynamic.py | 1 | 6 |
| lib_tomllib_flags.py | 1 | 6 |
| lib_tomllib_typed_callback.py | 1 | 6 |
| lib_tomllib_uncaught.py | 1 | 6 |
| lib_types_mappingproxy.py | 2 | 12 |
| lib_types_mappingproxy_opaque.py | 1 | 3 |
| upstream_tomllib_data.py | 1 | 6 |
| upstream_tomllib_misc.py | 1 | 6 |

The remaining four-obligation GC decrease belongs to the edited identity-boundary deviation and is reviewed separately with its moved observations. These are denominator changes, not newly proved obligations. Final-source census binding remains mandatory; no compiler/checker/runtime execution or broad IR normalization occurred in this review.
