# Tomllib guard attribution correction

The earlier IR disposition misidentified three guarded values as tuple pointers and their error as TypeError. Independent raw-IR review confirms that the values are `Output.flags` receivers and the error is **AttributeError**.

The seven corrected cases are 1736, 1737, 1738, 1739, 1741, 2557 and 2558. Each retains a receiver-null check before `Flags.add_pending`, the second `Flags.is_`, and `Flags.unset_all` in the respective parser rules. Tuple identity-header changes are separate.

The assembly script, accepted-IR report, combined disposition and their prose were corrected. The combined report now pins the updated accepted-review hash. All original raw IR/source/status hashes and case counts remain unchanged. The JSON correction receipt retains the earlier text and report hashes, corrected text/hashes, and exact per-case receiver, branch, call and AttributeError constants. It grants no new runtime or Lean proof and does not yet assert the before-pass removal-count association.
