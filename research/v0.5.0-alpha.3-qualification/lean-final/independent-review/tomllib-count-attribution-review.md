# Independent verification of the exact Tomllib null sites

All **21 sites across seven fixtures** match the raw old/new null-pass snapshots. Each of the three parser functions has four old removed-check obligations and three new ones. The only changed removal is an `Output.flags` receiver check: `create_dict_rule` checks `is_`, `create_list_rule` checks `unset_all`, and `key_value_rule` checks `add_pending`.

The same check operation occurs in both before-pass inputs. It is absent after the old pass and retained exactly after the new pass. I traced every check through its `ptr.cmp` to the loaded `Flags` receiver, field index 1 on `Output`, and the downstream method call using that receiver. All raise `AttributeError` on null. These are separate from the VTuple layout change.

This review independently rehashed the large raw snapshots, matched all 42 selected before/after pass records to their compact excerpts, verified publication's canonical full-function hashes including location metadata, and checked all other per-function null denominators are unchanged. JSON records every exact phase/site and input hash. No compiler or theorem checker ran; final fresh-census binding remains mandatory, and this does not waive any model residual.
