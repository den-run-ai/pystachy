"""Render the compact human entry point from the checked audit ledgers."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
old = json.loads((ROOT / "old-identity.json").read_text())
new = json.loads((ROOT / "new-identity.json").read_text())
c = json.loads((ROOT / "classification.json").read_text())
comparison = json.loads((ROOT / "comparison-previous.json").read_text())
tree = json.loads((ROOT / "final-tree.json").read_text())
counts = c["final_counts"]
lines = [
    "# Pystachy boundary integration: complete native IR audit", "",
    f"All **{c['total']:,} corpus inputs** were compiled with the pinned alpha2 and final native compilers. "
    f"There are **zero new rejections**, **{counts.get('new_acceptance', 0)} new acceptances**, "
    f"and **{counts.get('diagnostic_change', 0)} changed rejection diagnostics**. "
    "Every substantive IR difference is classified and retained. This is a compiler-output compatibility audit, not a claim that every corpus program was separately executed or that aliasing/GC semantics are proved.", "",
    "## Pinned identities", "",
    "| Item | Identity |", "|---|---|",
    f"| Baseline source | `{old['source_ref']}` |",
    f"| Audited local source | `{new['source_ref']}` |",
    f"| Published compiler source with identical tree | `{new['evidence']['published_ref']}` |",
    f"| Audited source tree | `{new['source_tree']}` |",
    f"| Final published source | `{tree['final_published']}` |",
    f"| Final published tree | `{tree['final_tree']}` |",
    f"| Baseline native compiler SHA256 | `{old['binary_sha256']}` |",
    f"| Candidate native compiler SHA256 | `{new['binary_sha256']}` |", "",
    "The baseline executable was built from the recorded predecessor with byte-identical tracked compiler, runtime and private-library inputs to alpha2; its manifest and bootstrap log are included. "
    "The candidate passed a fresh three-stage fixed point for both the compiler and runtime after the `vtuple.box` effect-contract correction. "
    "Its installed native binary matches stage2. The prepare step verified the published and local Git trees are identical. "
    "Complete source-file and binary hashes were checked before and after the full run.", "",
    "The final published head adds only the corrected strict-storage adapter, its generator negative controls, and its scope documentation after that native build. "
    "`final-tree.json` records the exact three paths, their before/after hashes and the final Git tree, and verifies that every compiler/runtime/library/corpus input and the native binary are unchanged. "
    "`final-tools.patch` retains that complete final delta. The native build source and final tools source are identified separately.", "",
    "## Complete coverage and results", "",
    f"The final inventory contains {c['corpus_inventory']['baseline_count']:,} baseline case paths plus "
    f"{len(c['corpus_inventory']['added_paths'])} added paths, with no removed case paths. "
    "The only modified existing source case is `tests/deviations/dynany_identity_boundary.py`: resolved tuple/optional-list observations were removed from the deviation fixture after gaining positive differential coverage. "
    "Both compilers receive the same final version of each case and the same prepared case import path, while each compiler reads its own pinned private library. "
    "The canonical runtime corpus is a verified subset of this larger IR corpus.", "",
    "| Classification | Cases |", "|---|---:|",
]
for key, value in counts.items():
    lines.append(f"| {key} | {value:,} |")
lines += ["",
    "`identical` means equality under the repository's `tools/irsame.sh` oracle, including its existing narrow diagnostic source-location rule. "
    "The raw oracle exits 1 when any difference exists; this expected exit is retained, not relabeled as a byte-identical pass. "
    "All acceptance changes and all three non-location diagnostic changes are added fixtures. Existing rejection wording/statuses remain unchanged apart from private-home source locations.", "",
    "The new acceptances cover demand-driven imported constructor dependencies, fixed-layout constructors within inheritance, recursive/quoted/imported hierarchy use, and boxed generic class identity across module boundaries. "
    "The three rejection diagnostics now reach more specific existing limitations: unsupported `Annotated` parameters, a remaining variable-layout constructor, and an actually requested invalid override. "
    "Their complete old/new messages are in `classification.md` and the raw archive.", "",
    "Substantive IR changes include nominal fixed-layout declarations and constructor/method naming, the extra runtime-tuple identity-companion header word, numeric tuple/list identity propagation, numeric generator promise companions, generic type checks, and conservative object-write effects. "
    "The effect changes retain additional null guards in TOML code because mutable object facts can no longer be reused across companion writes. "
    "Those additional guards and identity operations are reported as real generated-code changes; they are not normalized away.", "",
    "## Narrow location normalization", "",
    "Old/new snapshot home paths have exactly equal byte lengths. Before execution, every archived source file was scanned to exclude literal occurrences of those audit prefixes. "
    "The supplemental comparison rewrites only exact prefixes in recognized generated ImportError source-location constants or compiler-home/sys.prefix constants, and recognized diagnostic source-location shapes. "
    "It does not rewrite instructions, symbol names, array lengths, line numbers, arbitrary strings or type descriptors. "
    "Twenty-four remaining shared test/port import-path payload occurrences are left untouched and are independently recorded as verbatim-identical in the opposite IR. "
    "All raw messages, raw IR and raw diffs remain in the archive, so this supplemental judgment is independently reviewable.", "",
    "## Review finding and fresh qualification", "",
    "The preceding complete audit exposed a stale optional-list deviation recording, which was corrected and directly checked. "
    "Review also found that optional numeric widening through `pys_vtuple_box` can materialize the source identity companion while its compiler declaration advertised only `R A`. "
    "The declaration now includes `rO wO`; the focused heap-reaching regression fails under the old declaration and passes under the corrected declaration. "
    "The final bootstrap and this full audit use the corrected compiler inputs. The preceding run remains retained locally as superseded evidence.", "",
    "The final strict-storage adapter also recognizes canonical low/digits generator yield pairs when a third independent Dyn identity operand is present. "
    "The third operand remains checked, and generator returns retain their two-word contract. Independent actual-record mutation controls reject wrong pairing, wrong operand types, a fourth operand, tainted identity transport and a third return operand. "
    "This tools-only correction removes false low-word obligations; it does not claim generator identity or GC lifetime proofs.", "",
    f"Of {comparison['review_cases']} substantive/status/diagnostic review cases, {comparison['reusable']} matched the preceding reviewed old/new IR and diagnostics exactly after demonstrated equal-length generated-home replacements, with the same input source hash. "
    f"The {len(comparison['requires_review'])} remaining cases received fresh review. "
    "The complete per-side cross-audit hashes and every substituted line are retained in `comparison-previous.json`. No prior review is reused merely because a filename or category matches.", "",
    "## Publication files", "",
    "- `classification.md` explains every raw difference, including complete changed rejection diagnostics.",
    "- `raw-results.tar.xz` retains all 4,634 cases' statuses, source/IR/message hashes, modes and search paths, all diagnostics, and every changed old/new IR plus raw and supplemental diffs.",
    "- `manifests-and-ledgers.tar.xz` contains exhaustive old/new source identities, toolchain versions/hashes, full per-case JSONL ledgers, inventory, command/environment overrides, bootstrap logs, complete classification data, review evidence and a SHA256/size manifest for every raw archive member.",
    "- `bundle-manifest.json` hashes and sizes every publication file.",
    "- The text scripts preserve the exact preparation, two-worker run, inspection, cross-audit comparison and classification workflow. `original-irsame.sh` is the repository oracle; `retaining-irsame.sh` changes only evidence retention/reporting.", "",
    "The complete uncompressed snapshots and raw evidence remain under the audit directory recorded in the manifests. Equal outputs were removed only after their statuses, diagnostic hashes and complete IR hashes/byte sizes were recorded; every changed IR is retained.", "",
    "## Reproduction", "",
    "Use the pinned sources/binaries and toolchain recorded in the metadata archive. `prepare.py` creates isolated equal-length `home-old`/`home-new` source snapshots, validates fixed-point/build provenance and checks the full corpus against `tests/corpus.sh`. "
    "`run.py` executes the retained oracle with exactly two workers and rechecks every snapshot input afterward. "
    "Run `inspect.py` against the retained directory using `new-cases.txt` and the exact home pair recorded in the command manifest. "
    "The raw exit, complete timings and complete ordered ledger must be preserved. `compare_previous.py` and the per-case review files explain qualified review reuse; `classify.py` rejects missing reviews, unresolved cases or unexpected status categories. "
    "Absolute paths are part of generated source-location data and are deliberately recorded; a replay at a different path can have different raw path constants even when the supplemental comparison agrees.", "",
]
(ROOT / "README.md").write_text("\n".join(lines))
