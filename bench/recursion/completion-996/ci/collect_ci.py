#!/usr/bin/env python3
"""Read-only PR #996 CI metadata collection and offline exact-head evidence validation.

fetch uses only public GETs, includes all workflow events, and paginates every list.
verify needs a clean exact-head checkout and downloaded artifact ZIPs named as in
the artifact inventory. Connector downloads may supply those ZIPs; signed download
URLs are never inputs to, or outputs of, this script. No test/compiler is run: the
repository's report validators read the retained reports and enumerate contracts.
"""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile

REPO = "den-run-ai/pystachy"
WORKFLOWS = {"CI", "Coverage", "Lint", "Installation", "Packages", "Performance smoke", "DCO"}
EXPECTED_SKIPS = {"DCO certified (fork pull requests)", "publish main's coverage to the badges branch"}
CONDITIONAL_STEPS = {
    "Opt-in sweeps CPython oracle dependency": lambda group: group.startswith(("dynany-optin-", "python-int-optin-")),
    "Extended subset benchmark correctness": lambda group: group == "benchmarks",
    "Adapted pyperformance benchmark correctness": lambda group: group == "benchmarks",
    "Optional BLAS adapter and nanoGPT fused-linear correctness": lambda group: group == "benchmarks",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    assert not re.search(r"[?&](?:sig|token|X-Amz-Signature|X-Amz-Credential)=", text, re.I), "signed URL in evidence"
    path.write_text(text)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=30).stdout


def fetch(args):
    api = "https://api.github.com/repos/" + args.repo
    sources = []

    def get(path):
        url = api + path
        with urlopen(Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "pystachy-pr996-ci-evidence", "X-GitHub-Api-Version": "2022-11-28"}), timeout=30) as response:
            raw = response.read()
        sources.append({"url": url, "response_sha256": sha(raw)})
        return json.loads(raw)

    def pages(path, key, **query):
        records, total = [], None
        for page in range(1, 101):
            result = get(path + "?" + urlencode({**query, "per_page": 100, "page": page}))
            if total is None:
                total = result["total_count"]
            assert total == result["total_count"], "list changed during pagination"
            records.extend(result[key])
            if len(records) >= total:
                break
            assert result[key], "truncated API list"
        assert len(records) == total and len({r["id"] for r in records}) == total
        return {"total_count": total, key: records}

    raw = args.out / "raw"
    runs = pages("/actions/runs", "workflow_runs", head_sha=args.head)
    save(raw / "runs-all-events.json", runs)
    save(raw / "check-runs.json", pages("/commits/" + args.head + "/check-runs", "check_runs", filter="latest"))
    for run in runs["workflow_runs"]:
        run_id = str(run["id"])
        save(raw / ("jobs-" + run_id + ".json"), pages("/actions/runs/" + run_id + "/jobs", "jobs", filter="latest"))
        save(raw / ("artifacts-" + run_id + ".json"), pages("/actions/runs/" + run_id + "/artifacts", "artifacts"))
    save(raw / "head-commit.json", get("/git/commits/" + args.head))
    if args.merge:
        save(raw / "merge-commit.json", get("/git/commits/" + args.merge))
    save(args.out / "retrieval.json", {"method": "public GitHub REST GET, all events, complete pagination", "captured_utc": datetime.now(timezone.utc).isoformat(), "sources": sources})


def validate_checks(args):
    raw = args.out / "raw"
    runs = read(raw / "runs-all-events.json")
    checks = read(raw / "check-runs.json")
    assert runs["total_count"] == len(runs["workflow_runs"])
    assert checks["total_count"] == len(checks["check_runs"]) == args.expected_checks
    assert {r["name"] for r in runs["workflow_runs"]} == WORKFLOWS
    assert len(runs["workflow_runs"]) == len(WORKFLOWS), "unexpected reruns: select/document exact attempts explicitly"
    jobs, run_summary, skipped_steps = {}, [], []
    for run in runs["workflow_runs"]:
        expected_run = "skipped" if run["name"] == "DCO" else "success"
        assert run["head_sha"] == args.head and run["status"] == "completed" and run["conclusion"] == expected_run
        payload = read(raw / f"jobs-{run['id']}.json")
        assert payload["total_count"] == len(payload["jobs"])
        assert len({j["id"] for j in payload["jobs"]}) == len(payload["jobs"])
        for job in payload["jobs"]:
            assert job["head_sha"] == args.head and job["run_id"] == run["id"] and job["status"] == "completed"
            assert job["run_attempt"] == run["run_attempt"]
            assert job["conclusion"] == ("skipped" if job["name"] in EXPECTED_SKIPS else "success")
            if job["name"] == "DCO certified (fork pull requests)":
                assert run["event"] == "pull_request_target" and run["head_repository"]["full_name"] == args.repo
            if job["name"] == "publish main's coverage to the badges branch":
                assert run["event"] == "pull_request"
            group = job["name"][8:-1] if job["name"].startswith("verify (") else ""
            for step in job["steps"]:
                wanted = "success"
                if group and step["name"] in CONDITIONAL_STEPS:
                    wanted = "success" if CONDITIONAL_STEPS[step["name"]](group) else "skipped"
                assert step["status"] == "completed" and step["conclusion"] == wanted, (job["name"], step)
                if wanted == "skipped":
                    skipped_steps.append({"job_id": job["id"], "group": group, "step": step["name"], "reason": "matrix condition false; required in its designated group"})
            assert job["id"] not in jobs
            jobs[job["id"]] = job
        run_summary.append({k: run[k] for k in ("id", "name", "event", "status", "conclusion", "head_sha", "run_attempt", "html_url", "created_at", "updated_at")} | {"jobs": len(payload["jobs"])})
    assert set(jobs) == {c["id"] for c in checks["check_runs"]}, "jobs/checks do not have exact membership"
    rows = []
    for check in checks["check_runs"]:
        job = jobs[check["id"]]
        assert check["head_sha"] == args.head and check["status"] == "completed"
        assert check["name"] == job["name"] and check["conclusion"] == job["conclusion"]
        rows.append({k: check[k] for k in ("id", "name", "head_sha", "status", "conclusion", "details_url")} | {"workflow_run_id": job["run_id"]})
    assert {c["name"] for c in rows if c["conclusion"] == "skipped"} == EXPECTED_SKIPS
    save(args.out / "checks.json", {"total": len(rows), "conclusions": dict(Counter(c["conclusion"] for c in rows)), "checks": rows, "workflows": run_summary, "conditional_step_skips": skipped_steps})
    return runs["workflow_runs"], jobs, rows


def validate_archives(args, runs):
    inventory = {}
    for run in runs:
        path = args.out / "raw" / f"artifacts-{run['id']}.json"
        if not path.exists() and run["name"] == "DCO":
            continue  # Skipped workflow has no execution or downloadable evidence.
        payload = read(path)
        assert payload["total_count"] == len(payload["artifacts"])
        for artifact in payload["artifacts"]:
            assert artifact["workflow_run"]["head_sha"] == args.head and artifact["workflow_run"]["id"] == run["id"]
            assert artifact["name"] not in inventory
            inventory[artifact["name"]] = artifact
    verified = []
    for path in sorted((args.out / "artifacts").glob("*.zip")):
        artifact = inventory[path.stem]
        data = path.read_bytes()
        assert len(data) == artifact["size_in_bytes"] and "sha256:" + sha(data) == artifact["digest"], path
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None and len(set(archive.namelist())) == len(archive.namelist())
            if path.stem.startswith("verification-"):
                dest = args.out / "reports" / path.stem
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "verification.json").write_bytes(archive.read("verification.json"))
                for extra in ("pyperformance-smoke.json", "extended-smoke.json"):
                    if extra in archive.namelist():
                        (dest / extra).write_bytes(archive.read(extra))
            elif path.stem in ("verification", "perf-smoke", "port-check"):
                report = args.out / "artifacts" / (path.stem + ".json")
                content = archive.read(path.stem + ".json")
                if report.exists():
                    assert report.read_bytes() == content
                else:
                    report.write_bytes(content)
            verified.append({"name": path.stem, "artifact_id": artifact["id"], "workflow_run_id": artifact["workflow_run"]["id"], "bytes": len(data), "sha256": sha(data), "members": len(archive.namelist()), "crc_integrity": "pass", "github_digest_matches": True, "api_url": artifact["url"], "archive_file": path.relative_to(args.out).as_posix()})
    save(args.out / "artifact-verification.json", {"verified": verified, "metadata_only": [a for name, a in inventory.items() if name not in {v["name"] for v in verified}]})
    return verified


def validate_reports(args):
    root = args.source.resolve()
    assert git(root, "rev-parse", "HEAD").decode().strip() == args.head
    assert not git(root, "status", "--porcelain", "--untracked-files=all").strip(), "validator checkout is not clean"
    aggregate = read(args.out / "artifacts/verification.json")
    merge = read(args.out / "raw/merge-commit.json")
    head = read(args.out / "raw/head-commit.json")
    assert merge["sha"] == aggregate["git"]["commit"] == args.merge
    assert [p["sha"] for p in merge["parents"]] == [args.base, args.head]
    assert head["sha"] == args.head and merge["tree"]["sha"] == head["tree"]["sha"] == git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    assert aggregate["git"]["dirty"] is False and aggregate["ignored_env"] == []
    sys.path.insert(0, str(root / "tools"))
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("ci_merge_validator", root / "tools/merge_verification.py")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    groups = validator.load_groups()  # --list only; no tests or compiler.
    rebuilt = validator.merge_reports(args.out / "reports", groups, expected_commit=args.merge)
    validator.validate_report(aggregate, "all", groups["all"])
    # The merge is independently recomputed from every original group report. Only
    # wall-clock assembly time and download-root path prefixes differ locally.
    left, right = copy.deepcopy(aggregate), copy.deepcopy(rebuilt)
    left.pop("timestamp_utc"); right.pop("timestamp_utc")
    for value in (left, right):
        for group in value["ci"]["groups"]:
            group["report"] = Path(group["report"]).parent.name + "/verification.json"
        for step in value["steps"]:
            if isinstance(step.get("log"), str) and "verification-" in step["log"]:
                step["log"] = step["log"][step["log"].index("verification-"):]
    assert left == right, "local merge differs from the published aggregate beyond documented path/time fields"
    save(args.out / "remerged-verification.json", rebuilt)
    source_hashes = {}
    for path, item in aggregate["sources"].items():
        if isinstance(item, dict) and "sha256" in item:
            data = (root / path).read_bytes()
            assert sha(data) == item["sha256"] and len(data.splitlines()) == item["lines"], path
            source_hashes[path] = item["sha256"]
    with zipfile.ZipFile(args.out / "artifacts/verified-bootstrap.zip") as archive:
        manifest_bytes = archive.read("manifest.json")
        manifest = json.loads(manifest_bytes)
        bootstrap = aggregate["steps"][0]
        assert sha(manifest_bytes) == bootstrap["bootstrap_bundle_id"]
        assert manifest["identity"]["commit"] == args.merge
        ci_id = next(r["id"] for r in read(args.out / "raw/runs-all-events.json")["workflow_runs"] if r["name"] == "CI")
        assert manifest["identity"]["github_run_id"] == str(ci_id)
        for name, digest in manifest["sha256"].items():
            assert sha(archive.read(name)) == digest, name
        assert archive.read("rt1.ll") == archive.read("rt2.ll")
        assert manifest["sha256"]["stage1.ll"] == bootstrap["ir_sha256"]
        assert manifest["sha256"]["rt1.ll"] == bootstrap["runtime_ir_sha256"]
        save(args.out / "bootstrap-manifest.json", manifest)
    for step in aggregate["steps"]:
        if "python_int_optin" in step:
            assert step["python_int_optin"]["compiler_sha256"] == manifest["sha256"]["pystachy2"]
    summaries = []
    for step in aggregate["steps"]:
        row = {k: v for k, v in step.items() if isinstance(v, (int, float, bool, str)) and k not in ("log", "seconds")}
        for key in ("stressed_sample", "optin", "python_int_optin"):
            if key in step:
                row[key] = {k: v for k, v in step[key].items() if isinstance(v, (int, float, bool, str)) or k in ("failures", "modes")}
        summaries.append(row)
    save(args.out / "suite-counts.json", {"sources": {k: v for k, v in aggregate["sources"].items() if isinstance(v, int)}, "steps": summaries})
    save(args.out / "groups.json", {"contract": groups, "groups": aggregate["ci"]["groups"], "logical_stages": len(groups["all"]), "group_stage_executions": sum(len(v) for k, v in groups.items() if k != "all"), "all_original_group_reports_remerged": True, "aggregate_equal_except_assembly_timestamp_and_download_root": True})
    contract_paths = [*sorted(p.relative_to(root).as_posix() for p in (root / ".github/workflows").glob("*.yml")), "tests/verify.sh", "tools/merge_verification.py", "tools/verification_bootstrap.py", "tools/dynany_optin.py", "tools/python_int_gate.py"]
    contracts = [{"path": p, "commit": args.head, "sha256": sha((root / p).read_bytes()), "url": f"https://github.com/{args.repo}/blob/{args.head}/{p}"} for p in contract_paths]
    # pull_request_target selects the base workflow, not the pull request's copy.
    dco_base = git(root, "show", args.base + ":.github/workflows/dco.yml")
    assert b"if: github.event.pull_request.head.repo.full_name != github.repository" in dco_base
    assert b"github.ref == 'refs/heads/main' && github.event_name != 'pull_request'" in (root / ".github/workflows/coverage.yml").read_bytes()
    contracts.append({"path": ".github/workflows/dco.yml", "commit": args.base, "sha256": sha(dco_base), "url": f"https://github.com/{args.repo}/blob/{args.base}/.github/workflows/dco.yml"})
    save(args.out / "source-binding.json", {"head": args.head, "base": args.base, "merge": args.merge, "tree": head["tree"]["sha"], "merge_parents": [p["sha"] for p in merge["parents"]], "aggregate_source_hashes_checked": source_hashes, "contracts": contracts, "validator_source_commit": args.head, "source_checkout_clean": True})
    return aggregate, manifest, groups


def validate_coverage(args):
    rows = []
    for name, expected in (("coverage", {"cache", "ffi", "ir", "unit", *(f"corpus-{i}" for i in range(8))}), ("runtime-coverage", {"ffi", *(f"corpus-{i}" for i in range(6))})):
        with zipfile.ZipFile(args.out / "artifacts" / (name + ".zip")) as archive:
            parts = [json.loads(archive.read(p)) for p in archive.namelist() if p.startswith("parts/") and p.endswith(".json")]
            assert {p["part"] for p in parts} == expected and len(parts) == len(expected)
            for part in parts:
                assert part["commit"] == args.merge and part["dirty"] is False and part["selected"] is False
                assert part.get("data_files", part.get("profiles", 0)) > 0
                assert not re.search(r"[1-9][0-9]* failed|FAILED|Traceback", part["report"])
            assert sum(p["cases"] for p in parts if p["suite"] == "corpus") == read(args.out / "artifacts/verification.json")["sources"]["corpus_cases"]
            report, badge = json.loads(archive.read("coverage.json")), json.loads(archive.read("badge.json"))
            totals = report.get("totals") or report["data"][0]["totals"]
            rows.append({"name": name, "parts": parts, "totals": totals, "badge": badge})
    save(args.out / "coverage-summary.json", rows)
    return rows


def validate_lint(args, jobs):
    job = next(j for j in jobs.values() if j["name"].startswith("make lint"))
    logpath = args.out / "logs" / f"lint-{job['id']}.txt"
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", line.split("Z ", 1)[-1]) for line in logpath.read_text().splitlines()]
    suites, command = [], None
    for index, line in enumerate(lines):
        if "-m unittest discover " in line:
            command = line.removeprefix("##[group]Run ")
        match = re.fullmatch(r"Ran (\d+) tests? in ([0-9.]+)s", line)
        if match:
            assert command is not None and int(match[1]) > 0
            following = next(s for s in lines[index + 1:] if s.strip())
            assert following == "OK", (command, following)
            suites.append({"command": command, "tests": int(match[1]), "seconds": float(match[2]), "result": following})
    assert suites and "All checks passed!" in lines
    oracle = next(line for line in lines if re.fullmatch(r"CPython 3\.13\.16: \d+ recordings, \d+ deviations, \d+ files of lib/ checked; 0 failed", line))
    result = {"job_id": job["id"], "url": job["html_url"], "suite_invocations": len(suites), "tests": sum(s["tests"] for s in suites), "unittest_skips": 0, "suites": suites, "oracle_recordings": oracle, "mypy": next(s for s in lines if s.startswith("Success: no issues found")), "runtime_roots": next(s for s in lines if "static pointer stores: 0 GC root problems" in s), "log_sha256": sha(logpath.read_bytes())}
    save(args.out / "lint-tests.json", result)
    return result


def verify(args):
    runs, jobs, checks = validate_checks(args)
    archives = validate_archives(args, runs)
    report, bootstrap, groups = validate_reports(args)
    coverage = validate_coverage(args)
    lint = validate_lint(args, jobs)
    port = read(args.out / "artifacts/port-check.json")
    assert port["result"] == "pass" and all(m["passed"] == m["tests_run"] and not m["skipped"] for m in port["modules"])
    perf = read(args.out / "artifacts/perf-smoke.json")
    assert perf["status"] == perf["phase"] == "complete" and perf["revisions"] == {"base": args.base, "head": args.merge}
    extra = []
    for name, key in (("extended-smoke", "cases"), ("pyperformance-smoke", "benchmarks")):
        result = read(args.out / "reports/verification-benchmarks" / (name + ".json"))
        assert result["status"] == "ok" and result["metadata"]["git_revision"] == args.merge
        extra.append({"name": name, "status": "ok", "cases": len(result[key])})
    summary = {
        "schema": 1, "status": "verified", "purpose": "Historical exact-head CI correctness checkpoint; no performance acceptance decision",
        "repository": args.repo, "pull_request": 996, "head": args.head, "base": args.base, "synthetic_merge": args.merge,
        "tree": read(args.out / "raw/head-commit.json")["tree"]["sha"], "merge_tree_equals_head_tree": True,
        "workflow_runs": len(runs), "check_runs": len(checks), "conclusions": dict(Counter(c["conclusion"] for c in checks)),
        "expected_skips": {"DCO certified (fork pull requests)": "same-repository branch; base workflow condition false", "publish main's coverage to the badges branch": "pull-request event; publication is restricted to main"},
        "verification": {"logical_stages": len(report["steps"]), "groups": len(groups) - 1, "group_stage_executions": sum(len(v) for k, v in groups.items() if k != "all"), "reused_bootstrap_validations": len(groups) - 2, "failed": 0, "all_original_reports_remerged": True, "expected_counts_and_source_identities_validated": True, "corpus_counts": {k: v for k, v in report["sources"].items() if isinstance(v, int)}, "toolchain": report["toolchain"]},
        "bootstrap": {"bundle_id": report["steps"][0]["bootstrap_bundle_id"], "native_sha256": bootstrap["sha256"]["pystachy2"], "compiler_ir_sha256": bootstrap["sha256"]["stage1.ll"], "runtime_ir_sha256": bootstrap["sha256"]["rt1.ll"], "all_bundle_member_hashes_verified": True},
        "lint": {k: lint[k] for k in ("suite_invocations", "tests", "unittest_skips", "oracle_recordings", "mypy", "runtime_roots")},
        "coverage": [{"name": r["name"], "parts": len(r["parts"]), "badge": r["badge"]["message"]} for r in coverage],
        "extra_benchmark_correctness": extra, "port_preservation": port["modules"],
        "artifacts": {"archives_verified": len(archives), "bytes": sum(a["bytes"] for a in archives), "sha256_size_and_zip_crc_verified": True},
        "references": {"checks": "checks.json", "groups": "groups.json", "suite_counts": "suite-counts.json", "lint_tests": "lint-tests.json", "coverage": "coverage-summary.json", "artifacts": "artifact-verification.json", "source_binding": "source-binding.json"},
        "limitations": ["This evidence belongs only to the named head/tree, not to later commits.", "Successful performance-smoke execution is a checksum/completion result, not performance acceptance.", "Opt-in completed checks include documented exact expected compiler rejections and AOT native-IR deferrals; those categories are preserved in suite-counts.json and validated against the complete native suite.", "Coverage percentages are report-only; coverage part membership, test reports and source commit were verified.", "Coverage intermediate data archives were inventoried; the combined coverage archives retain their original per-part reports/logs.", "The bootstrap archive retains stage1 compiler IR and equal runtime stage1/stage2 IR; compiler fixed-point equality is attested by the successful producer report/log, not a separately retained stage2 compiler IR file."],
        "collector_sha256": sha(Path(__file__).read_bytes()),
    }
    save(args.out / "summary.json", summary)
    manifest = {p.relative_to(args.out).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in sorted(args.out.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    save(args.out / "manifest.json", {"schema": 1, "files": manifest})
    print(json.dumps({"status": summary["status"], "head": args.head, "checks": len(checks), "conclusions": summary["conclusions"], "groups": len(groups) - 1, "stages": len(report["steps"]), "lint_tests": lint["tests"], "archives_verified": len(archives)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("fetch", "verify"))
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base")
    parser.add_argument("--merge")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--expected-checks", type=int, default=61)
    args = parser.parse_args()
    args.out = args.out.resolve()
    if args.phase == "verify":
        assert args.source and args.base and args.merge
        verify(args)
    else:
        fetch(args)


if __name__ == "__main__":
    main()
