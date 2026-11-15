"""Render the premerge README only from complete, independently accepted evidence."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEAN = ROOT / "evidence/lean-storage-corrected"
SOURCE = "0a2fe77a580106c197face4d2904be80e3f85dbc"
TREE = "107460d5f89bdcf37f2741b233eac0568d82604a"
INTEGRATED = "328b945f02788b296d9981d1b44706a2a0092255"
BASELINE = "80490143498d149d407343ba1cb7aedb1db2d2c5"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accepted(path, status):
    result = read(path)
    assert result["status"] == status, str(path)
    assert result["checks"] and all(result["checks"].values()), str(path)
    return result


acceptance = read(LEAN / "acceptance.json")
assert acceptance["commit"] == SOURCE and acceptance["tree"] == TREE
assert acceptance["checks"] and all(acceptance["checks"].values())
assert acceptance["programs"] == 2699 and acceptance["storage_programs"] == 196
assert not acceptance["storage_gaps"] and not acceptance["failed_records"]
assert not acceptance["incomplete_records"] and not acceptance["invalid_records"]
assert sha(LEAN / "records.jsonl") == acceptance["records_sha256"]
assert sha(LEAN / "report.md") == acceptance["report_sha256"]
receipt = accepted(LEAN / "final-census-receipt.json", "complete_and_strict_storage_accepted")
binding = accepted(LEAN / "count-attribution/final-census-binding.json", "bound_to_complete_final_source_census")
semantic = accepted(LEAN / "semantic-disposition.json", "reviewed_with_explicit_model_limits")
independent = accepted(LEAN / "independent-review/final-acceptance.json", "accepted_with_explicit_model_limits")
assert not receipt["prior_checker_records_reused"]
for record in (receipt, binding, semantic):
    assert record["candidate_commit"] == SOURCE and record["candidate_tree"] == TREE
assert len(semantic["denominator_dispositions"]) == 38

ci_path = ROOT / "evidence/ci/pr1494-storage/qualification.json"
repair_path = ROOT / "evidence/ci/pr1501/qualification.json"
ci, repair = read(ci_path), read(repair_path)
for record, head in ((ci, INTEGRATED), (repair, SOURCE)):
    assert record["head"] == head and record["status"] == "all_observed_runs_completed"
    assert not record["failures"]
    for name in ("CI", "Lint", "Submission format"):
        assert record["gate_statuses"][name]["status"] == "completed"
        assert record["gate_statuses"][name]["conclusion"] == "success"
assert ci["base"] == BASELINE
assert ci["gate_statuses"]["CodeQL"]
assert all(row["status"] == "completed" and row["conclusion"] == "success"
           for row in ci["gate_statuses"]["CodeQL"])
job_counts = Counter(job["conclusion"] for job in ci["jobs"])
repair_counts = Counter(job["conclusion"] for job in repair["jobs"])
assert set(job_counts) == set(repair_counts) == {"success", "skipped"}
assert all(job["status"] == "completed" for record in (ci, repair) for job in record["jobs"])

storage = acceptance["full_proof_totals"]["storage"]
assert storage["proved"] == storage["obligations"]
attempts = len(receipt["attempts"])
placeholders = {
    "__REQUIRED_FINAL_CENSUS_RESULT_COUNTS_HASHES__": (
        f"2,699 programs; 196 strict-storage selections; **{storage['proved']:,}/{storage['obligations']:,} storage obligations proved**; "
        f"all {len(acceptance['checks'])} acceptance checks true, no failed/incomplete/error records or storage gaps. "
        f"{attempts} recorded final-source execution attempt(s), with every attempt and any same-source resumed prefix retained. "
        f"Records SHA256 `{acceptance['records_sha256']}`; report SHA256 `{acceptance['report_sha256']}`. "
        "[Census receipt](lean-final/final-census-receipt.json), [acceptance](lean-final/acceptance.json), [report](lean-final/report.md)."),
    "__REQUIRED_FINAL_CENSUS_SOURCE_AND_INPUT_BINDING__": (
        f"Clean `{SOURCE}` / tree `{TREE}`; exact full corpus, input, Python and checker identities accepted. "
        "The optional-tuple target proves 142/142 in the fresh full census; zero unknown-count storage functions remain. "
        "[Source-bound census receipt](lean-final/final-census-receipt.json)."),
    "__REQUIRED_FINAL_DENOMINATOR_BINDING_RECEIPT_HASH_RESULT__": (
        f"All 38 decreases reviewed; {len(binding['rows'])} per-side extraction rows and "
        f"{len(binding['supported_decrease_pairs'])} selected null/GC/storage pairs bind to exact final census snapshots/counts; "
        "the separate access decrease retains its source/IR review. Binding SHA256 "
        f"`{sha(LEAN / 'count-attribution/final-census-binding.json')}`. "
        "[Binding](lean-final/count-attribution/final-census-binding.json), [semantic disposition](lean-final/semantic-disposition.md)."),
    "__REQUIRED_FINAL_INDEPENDENT_REVIEW_RECEIPTS_AND_FINDINGS__": (
        "Independent final acceptance is `accepted_with_explicit_model_limits`, with every check true and final evidence hashes bound. "
        f"Receipt SHA256 `{sha(LEAN / 'independent-review/final-acceptance.json')}`. "
        "The enumerated model residuals remain unproved. "
        "[Independent review](lean-final/independent-review/final-acceptance.md), [receipt](lean-final/independent-review/final-acceptance.json)."),
    "__REQUIRED_REPAIR_PR_FINAL_CHECKS__": (
        f"Exact repair head `{SOURCE}`: {repair_counts['success']} successful jobs and {repair_counts['skipped']} source-verified conditional skips. "
        "CI, Lint and both Submission runs passed before the normal expected-head merge. Codex's ready-triggered attempt failed for account quota, not a completed review. "
        "[Checks](repair-final-pr-checks.md), [merge identity](final-merged-tree-equivalence.json)."),
    "__REQUIRED_INTEGRATED_HEAD_SHA_TREE_AND_CI_REVIEW__": (
        f"Head `{INTEGRATED}` / tree `{TREE}`: {job_counts['success']} successful jobs and {job_counts['skipped']} source-verified conditional skips. "
        "CI, Lint, Submission, managed CodeQL workflow and aggregate passed; no new CodeQL alerts. "
        "[Complete checkpoint](integrated-final-pr-checks.md) retains every job/step, pagination, review state and the understood 300-file overlay warning. "
        "A fresh live head/base/review check remains mandatory immediately before merging."),
    "__REQUIRED_FINAL_PREMERGE_DISPOSITION__": (
        "The frozen source is accepted for ready-for-review and normal expected-head merge, with the explicit bounded-model limits below. "
        "Exact-main qualification and publication audits remain separate gates; this premerge record does not claim the release is published."),
}

template_path = ROOT / "evidence/premerge-qualified-README.template.md"
text = template_path.read_text()
for key, value in placeholders.items():
    assert text.count(key) == 1, key
    text = text.replace(key, value)
old = "**UNFINALIZED TEMPLATE. Final qualification is not established here. Every `__REQUIRED_...__` value must be replaced with verified evidence before this becomes the accepted premerge record. Alpha.3 publication remains a later gate.**"
assert old in text
text = text.replace(old, "**Premerge qualification accepted with explicit model limits.** The complete fresh census, exact source bindings and independent final review are accepted below. Alpha.3 publication remains a later gate.")
old = "The census continues on **0a2f**, retaining that execution identity."
if old in text:
    text = text.replace(old, "The census completed on **0a2f**, retaining that execution identity.")
text = text.replace("the census continues on **0a2f**, retaining that execution identity.",
                    "the census completed on **0a2f**, retaining that execution identity.")
text = text.replace("Main remains at **80490143**. Integrated PR #1494 CI on **328b945f** is pending.",
                    f"The recorded main base is **80490143**. Integrated PR #1494 CI on **328b945f** passed; its complete snapshot was observed at {ci['observed_utc']}.")
text = text.replace("The fresh **0a2f** census has separate records and checker/input identities. Its final outcome is deliberately unresolved below.",
                    "The complete fresh **0a2f** census has separate records and checker/input identities. Its final acceptance and independent review are recorded below; no prior-checker census records were reused.")
text = text.replace("The final census must reconcile these residuals explicitly.",
                    "The final census reconciles these exact residuals explicitly in the semantic disposition.")
text = text.replace("**all seven required workflows on the exact merged main SHA**.",
                    "**all seven required workflows on the exact merged main SHA**: CI, Installation, Lint, Packages, Performance smoke, Variants and Coverage.")
old = "Prepared with ChatGPT assistance. Finalization requires every placeholder above to be resolved, linked files and hashes validated, and the full final evidence independently reviewed."
assert old in text
text = text.replace(old, "Prepared with ChatGPT assistance. The frozen final evidence package also requires a separate link/hash audit and a live GitHub check immediately before the expected-head merge.")
assert all(marker not in text for marker in ("__REQUIRED_", "UNFINALIZED TEMPLATE", "deliberately unresolved", "CI on **328b945f** is pending"))
output = ROOT / "evidence/premerge-qualified-README.md"
assert not output.exists(), "Preserve an existing finalized README rather than overwriting it."
output.write_text(text)
print(json.dumps({"created_utc": datetime.now(timezone.utc).isoformat(), "path": str(output),
                  "sha256": sha(output), "words": len(text.split()), "source": SOURCE,
                  "integrated_head": INTEGRATED, "publication_claimed": False}, indent=2))
