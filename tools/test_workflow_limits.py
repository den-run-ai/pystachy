"""Cap PRs at 20 jobs, task groups at two workers, and every job at 15 minutes."""

import ast
from collections import Counter
import itertools
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 15
PR_LIMIT = 20
PR_EVENTS = ("pull_request", "pull_request_target")
PR_AXIS = re.compile(
    r"\$\{\{\s*fromJSON\(github\.event_name\s*==\s*'pull_request'\s*"
    r"&&\s*'([^']*)'\s*\|\|\s*'([^']*)'\)\s*\}\}"
)


def workflows() -> dict:
    paths = sorted(path for suffix in ("*.yml", "*.yaml")
                   for path in (ROOT / ".github/workflows").glob(suffix))
    # BaseLoader preserves "on" and scalar matrix values instead of using YAML 1.1 booleans.
    return {path.name: yaml.load(path.read_text(), Loader=yaml.BaseLoader) for path in paths}


def scalar(value):
    if not isinstance(value, str) or "${{" in value:
        raise ValueError(f"unsupported matrix value: {value!r}")
    return value


def matrix_rows(job: dict, event: str) -> list[dict]:
    """Expand static matrices and the explicit PR/full JSON axes used by CI."""
    if "uses" in job:
        raise ValueError("reusable workflow jobs need an explicit job budget")
    strategy = job.get("strategy", {})
    if not isinstance(strategy, dict):
        raise ValueError("unsupported job strategy")
    if "matrix" not in strategy:
        return [{}]
    matrix = strategy["matrix"]
    if not isinstance(matrix, dict):
        raise ValueError("unsupported dynamic matrix")
    axes = {}
    for name, values in matrix.items():
        if name in ("include", "exclude"):
            continue
        scalar(name)
        if isinstance(values, str):
            match = PR_AXIS.fullmatch(values)
            if not match:
                raise ValueError(f"unsupported dynamic matrix axis: {name}")
            values = json.loads(match[1] if event == "pull_request" else match[2])
        if not isinstance(values, list) or not values:
            raise ValueError(f"matrix axis {name} must be a nonempty list")
        axes[name] = [scalar(value) for value in values]

    filters = {}
    for kind in ("include", "exclude"):
        entries = matrix.get(kind, [])
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise ValueError(f"unsupported matrix {kind}")
        filters[kind] = [{scalar(key): scalar(value) for key, value in entry.items()} for entry in entries]
    if any(set(entry) - axes.keys() for entry in filters["exclude"]):
        raise ValueError("matrix exclude names an unknown axis")

    originals = [dict(zip(axes, values)) for values in itertools.product(*axes.values())] if axes else []
    originals = [row for row in originals if not any(
        all(row[key] == value for key, value in entry.items()) for entry in filters["exclude"])]
    rows = [dict(row) for row in originals]
    extra = []
    for entry in filters["include"]:
        matched = False
        for original, row in zip(originals, rows):
            # Includes may replace earlier include metadata, never original axis values.
            if all(key not in original or original[key] == value for key, value in entry.items()):
                row.update(entry)
                matched = True
        if not matched:
            extra.append(entry)
    if not rows and not extra:
        raise ValueError("empty matrix")
    return rows + extra


def known_skip(condition: str, event: str) -> bool:
    condition = condition.strip()
    if condition.startswith("${{") and condition.endswith("}}"):
        condition = condition[3:-2].strip()
    if condition == "false":
        return True
    match = re.fullmatch(r"github\.event_name\s*(==|!=)\s*'pull_request'", condition)
    if match:
        return (event == "pull_request") != (match[1] == "==")
    return False  # Unknown conditions may run; they cannot reduce the budget.


def pr_job_counts(found: dict) -> tuple[dict, dict]:
    counts, groups = {}, {}
    for filename, workflow in found.items():
        events = workflow.get("on", [])
        if isinstance(events, str):
            events = [events]
        if not isinstance(events, (dict, list)):
            raise ValueError(f"{filename}: unsupported workflow triggers")
        for event in PR_EVENTS:
            if event not in events:
                continue
            # Ignore paths and unknown conditions: a PR can touch every relevant file.
            for name, job in workflow["jobs"].items():
                label = f"{filename}/{event}/{name}"
                rows = matrix_rows(job, event)
                skipped = known_skip(job.get("if", ""), event)
                counts[label] = 1 if skipped else len(rows)  # A skipped job still creates a check row.
                if name == "verification" and not skipped:
                    if any(not row.get("group") for row in rows):
                        raise ValueError(f"{label}: verification matrix needs explicit groups")
                    for group, count in Counter(re.sub(r"-\d+$", "", row["group"]) for row in rows).items():
                        groups[f"{label}/{group}"] = count
                else:
                    groups[label] = counts[label]
    return counts, groups


def require_pr_budget(found: dict) -> dict:
    counts, groups = pr_job_counts(found)
    if sum(counts.values()) > PR_LIMIT:
        raise ValueError(f"PR job budget {sum(counts.values())} exceeds {PR_LIMIT}: {counts}")
    over = {name: count for name, count in groups.items() if count > 2}
    if over:
        raise ValueError(f"PR task groups exceed two workers: {over}")
    return counts


def require_timeouts(found: dict) -> None:
    for filename, workflow in found.items():
        for name, job in workflow["jobs"].items():
            minutes = job.get("timeout-minutes", "")
            if not isinstance(minutes, str) or not re.fullmatch(r"[1-9][0-9]*", minutes) or int(minutes) > LIMIT:
                raise ValueError(f"{filename}/{name}: timeout-minutes must be 1..{LIMIT}, got {minutes!r}")


class BudgetTests(unittest.TestCase):
    def workflow(self, matrix=None, **job):
        current = {"timeout-minutes": "15", **job}
        if matrix is not None:
            current["strategy"] = {"matrix": matrix, "max-parallel": "2"}
        return {"fixture.yml": {"on": {"pull_request": {"paths": ["only-this-file"]}}, "jobs": {"work": current}}}

    def test_yaml_preserves_on_and_job_timeout_not_step_timeout(self):
        workflow = yaml.load("on: [push, pull_request]\njobs:\n  work:\n    timeout-minutes: 15\n"
                             "    steps:\n      - run: echo ok\n        timeout-minutes: 99\n", Loader=yaml.BaseLoader)
        require_timeouts({"fixture.yml": workflow})
        self.assertEqual(sum(require_pr_budget({"fixture.yml": workflow}).values()), 1)

    def test_former_variants_matrix_is_24_jobs_despite_max_parallel(self):
        found = self.workflow({"variant": ["opt-1", "opt-2", "opt-3", "opt-4", "opt-5", "cflags-O0"],
                               "shard": ["0/4", "1/4", "2/4", "3/4"]})
        self.assertEqual(sum(pr_job_counts(found)[0].values()), 24)
        with self.assertRaisesRegex(ValueError, "PR job budget 24"):
            require_pr_budget(found)

    def test_boolean_filter_axis_does_not_hide_variant_cross_product(self):
        matrix = yaml.load("variant: [a, b, c, d, e, f]\nshard: [0, 1, 2, 3]\n"
                           "enabled: [true, false]\nexclude:\n  - enabled: false\n", Loader=yaml.BaseLoader)
        self.assertEqual(sum(pr_job_counts(self.workflow(matrix))[0].values()), 24)

    def test_include_only_matrix_and_partial_excludes(self):
        self.assertEqual(matrix_rows({"strategy": {"matrix": {"include": [{"os": "a"}, {"os": "b"}]}}},
                                     "pull_request"), [{"os": "a"}, {"os": "b"}])
        matrix = {"os": ["linux", "mac"], "python": ["3.12", "3.13"],
                  "exclude": [{"os": "mac"}],
                  "include": [{"mode": "release"}, {"os": "linux", "mode": "debug"},
                              {"os": "windows", "python": "3.13"}]}
        self.assertEqual(matrix_rows({"strategy": {"matrix": matrix}}, "pull_request"),
                         [{"os": "linux", "python": "3.12", "mode": "debug"},
                          {"os": "linux", "python": "3.13", "mode": "debug"},
                          {"os": "windows", "python": "3.13"}])

    def test_dynamic_axes_select_only_the_declared_event_branch(self):
        matrix = {"os": "${{ fromJSON(github.event_name == 'pull_request' && '[\"linux\"]' || '[\"linux\",\"mac\"]') }}",
                  "shard": ["0", "1"]}
        job = {"strategy": {"matrix": matrix}}
        self.assertEqual(len(matrix_rows(job, "pull_request")), 2)
        self.assertEqual(len(matrix_rows(job, "push")), 4)
        self.assertEqual(len(matrix_rows(job, "pull_request_target")), 4)

    def test_budget_sums_workflows_and_both_pr_event_types(self):
        found = self.workflow()
        found["target.yml"] = {"on": "pull_request_target", "jobs": {"dco": {}}}
        self.assertEqual(sum(require_pr_budget(found).values()), 2)
        found["target.yml"]["on"] = list(PR_EVENTS)
        self.assertEqual(sum(require_pr_budget(found).values()), 3)
        found["fixture.yml"]["jobs"] = {f"job-{n}": {} for n in range(19)}
        with self.assertRaisesRegex(ValueError, "PR job budget 21"):
            require_pr_budget(found)

    def test_known_skips_count_one_check_unknown_conditions_count_every_row(self):
        for condition, count in (("github.event_name != 'pull_request'", 1), ("${{ false }}", 1),
                                 ("github.event.pull_request.head.repo.fork", 2)):
            with self.subTest(condition=condition):
                found = self.workflow({"worker": ["0", "1"]}, **{"if": condition})
                self.assertEqual(sum(require_pr_budget(found).values()), count)

    def test_no_more_than_two_shards_per_verification_group(self):
        found = self.workflow({"group": ["native-0", "native-1", "safety-0", "safety-1"]})
        found["fixture.yml"]["jobs"]["verification"] = found["fixture.yml"]["jobs"].pop("work")
        self.assertEqual(sum(require_pr_budget(found).values()), 4)
        matrix = found["fixture.yml"]["jobs"]["verification"]["strategy"]["matrix"]
        matrix["group"].append("native-2")
        with self.assertRaisesRegex(ValueError, "exceed two workers"):
            require_pr_budget(found)
        matrix["group"].pop()
        matrix["machine"] = ["x86_64", "aarch64"]
        with self.assertRaisesRegex(ValueError, "exceed two workers"):
            require_pr_budget(found)

    def test_other_matrices_cannot_exceed_two_workers(self):
        with self.assertRaisesRegex(ValueError, "exceed two workers"):
            require_pr_budget(self.workflow({"worker": ["0", "1", "2"]}))

    def test_unknown_dynamic_matrices_and_reusable_workflows_fail_closed(self):
        for matrix in ("${{ fromJSON(needs.plan.outputs.matrix) }}",
                       {"worker": "${{ fromJSON(inputs.workers) }}"},
                       {"enabled": ["${{ github.event_name == 'pull_request' }}"]},
                       {"worker": [{"count": "2"}]},
                       {"worker": ["0"], "exclude": [{"unknown": "yes"}]}, {}):
            with self.subTest(matrix=matrix), self.assertRaises(ValueError):
                require_pr_budget(self.workflow(matrix))
        with self.assertRaisesRegex(ValueError, "reusable workflow"):
            require_pr_budget(self.workflow(uses="./.github/workflows/reusable.yml"))

    def test_missing_dynamic_and_long_timeouts_fail_including_releases(self):
        for minutes in (None, "", "0", "16", "25", "${{ inputs.minutes }}"):
            found = {"release.yml": {"on": {"push": {"tags": ["v*"]}},
                                     "jobs": {"publish": {"timeout-minutes": minutes}}}}
            with self.subTest(minutes=minutes), self.assertRaisesRegex(ValueError, "timeout-minutes"):
                require_timeouts(found)


class LimitTests(unittest.TestCase):
    def test_found(self):
        found = workflows()
        self.assertIn("ci.yml", found)
        self.assertIn("verification", found["ci.yml"]["jobs"])

    def test_every_job_has_a_timeout_of_at_most_fifteen_minutes(self):
        require_timeouts(workflows())

    def test_worst_case_pr_job_and_worker_budget(self):
        self.assertTrue(require_pr_budget(workflows()))

    def test_gc_identity_and_jit_jobs_are_separate_only_in_full_verification(self):
        job = workflows()["ci.yml"]["jobs"]["verification"]
        groups = {f"gc-{kind}-{shard}" for kind in ("ir", "jit") for shard in (0, 1)}
        for event in ("push", "workflow_dispatch"):
            with self.subTest(event=event):
                selected = [(row["machine"], row["group"]) for row in matrix_rows(job, event)
                            if row["group"] in groups]
                self.assertCountEqual(selected, itertools.product(("x86_64", "aarch64"), groups))
        self.assertFalse(groups & {row["group"] for row in matrix_rows(job, "pull_request")})
        self.assertEqual(job["env"]["VERIFY_PROFILE"],
                         "${{ github.event_name == 'pull_request' && 'pr' || 'full' }}")

    def test_o1_bootstrap_qualification_follows_standard_export_in_existing_x86_job(self):
        job = workflows()["ci.yml"]["jobs"]["bootstrap"]
        steps = job["steps"]
        probes = [step for step in steps if "tools/check_bootstrap_tier.py" in step.get("run", "")]
        self.assertEqual(len(probes), 1)
        probe = probes[0]
        self.assertEqual(probe["if"], "steps.plan.outputs.kind == 'code' && matrix.machine == 'x86_64'")
        self.assertIn("build/ci-bootstrap", probe["run"])
        self.assertNotIn("continue-on-error", probe)
        self.assertNotIn("continue-on-error", job)
        exports = [step for step in steps if "verification_bootstrap.py export build/ci-bootstrap" in step.get("run", "")]
        self.assertEqual(len(exports), 1)
        self.assertLess(steps.index(exports[0]), steps.index(probe))
        reports = [step for step in steps if "build/bootstrap-tier/report.json" in step.get("with", {}).get("path", "")]
        self.assertEqual(len(reports), 1)
        self.assertIn("build/bootstrap-tier/make.log", reports[0]["with"]["path"])
        self.assertIn("!cancelled()", reports[0]["if"])

    def test_lint_overlaps_exactly_two_control_suites_on_every_event(self):
        steps = workflows()["lint.yml"]["jobs"]["lint"]["steps"]
        controls = [step for step in steps if "test_*verif*.py" in step.get("run", "")]
        self.assertEqual(len(controls), 1)
        control = controls[0]
        self.assertNotIn("if", control)  # Includes docs-only PRs, main and manual runs.
        self.assertNotIn("continue-on-error", control)
        commands = "\n".join(step.get("run", "") for step in steps)
        for pattern in ("test_*verif*.py", "test_compiler_state*.py"):
            self.assertEqual(commands.count(pattern), 1)
        self.assertEqual(control["run"].splitlines(), [
            "python3 -m unittest discover -s tools -p test_lint_controls.py",
            "python3 tools/lint_controls.py 'test_*verif*.py' 'test_compiler_state*.py'",
        ])

    def test_generated_asan_runs_once_in_existing_x86_contracts_job(self):
        found = workflows()
        job = found["ci.yml"]["jobs"]["verification"]
        controls = [step for step in job["steps"] if "test_runtime_asan.py" in step.get("run", "")]
        self.assertEqual(len(controls), 1)
        control = controls[0]
        self.assertEqual(control["if"], "matrix.group == 'contracts' && matrix.machine == 'x86_64'")
        self.assertEqual(job["env"]["PYSTACHY_LLVM"], "/usr/lib/llvm-18/bin")
        self.assertEqual(control["run"].splitlines(), [
            "sudo apt-get update && sudo apt-get install -y libclang-rt-18-dev",
            "python3 -m unittest discover -s tools -p test_runtime_asan.py -v",
        ])
        for event in ("pull_request", "push", "workflow_dispatch"):
            self.assertEqual(sum(row["group"] == "contracts" and row["machine"] == "x86_64"
                                 for row in matrix_rows(job, event)), 1)
        self.assertNotIn("continue-on-error", control)
        self.assertNotIn("continue-on-error", job)
        toolchains = [step for step in job["steps"] if "tools/setup.sh --minimal" in step.get("run", "")]
        self.assertEqual(len(toolchains), 1)
        self.assertLess(job["steps"].index(toolchains[0]), job["steps"].index(control))

    def test_lint_runtime_discovery_omits_only_asan_and_preserves_failure(self):
        steps = workflows()["lint.yml"]["jobs"]["lint"]["steps"]
        controls = [step for step in steps if "test_runtime_*.py" in step.get("run", "")]
        self.assertEqual(len(controls), 1)
        control = controls[0]
        self.assertNotIn("if", control)
        self.assertNotIn("continue-on-error", control)
        self.assertIn('PYSTACHY_CACHE_TEST_LLVM="$PYSTACHY_LLVM" python3 -', control["run"])
        self.assertIn("<<'PY'\n", control["run"])
        script = control["run"].split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        paths = [*sorted((ROOT / "tools").glob("test_runtime_*.py")), Path("test_runtime_added.py")]
        self.assertIn("test_runtime_asan.py", [path.name for path in paths])
        expected = [path.name for path in paths if path.name != "test_runtime_asan.py"]
        for success in (True, False):
            with self.subTest(success=success), patch.object(Path, "glob", return_value=iter(paths)), \
                    patch.object(unittest.defaultTestLoader, "discover", return_value=unittest.TestSuite()) as discover, \
                    patch.object(unittest, "TextTestRunner") as runner:
                runner.return_value.run.return_value.wasSuccessful.return_value = success
                with self.assertRaises(SystemExit) as raised:
                    exec(compile(script, "<Lint runtime discovery>", "exec"), {})
                self.assertEqual(raised.exception.code, not success)
                self.assertCountEqual(discover.call_args_list,
                                      [unittest.mock.call("tools", pattern=name) for name in expected])

    def test_program_cache_probe_runs_once_per_machine_outside_compact_gc(self):
        # Full runs probe on both architectures' runtime-cache jobs; a pull request probes once,
        # in the first native JIT worker, outside the contracts and compact cache/GC jobs.
        jobs = workflows()["ci.yml"]["jobs"]
        for event in ("pull_request", "push", "workflow_dispatch"):
            selected = []
            for name in ("verification", "pr-variants"):
                job = jobs[name]
                probes = [step for step in job["steps"] if "make test-program-cache " in step.get("run", "")]
                self.assertEqual(len(probes), 1, name)
                probe = probes[0]
                self.assertIn("PROGRAM_CACHE_COMPILER=build/verify/pystachy2", probe["run"])
                self.assertNotIn("continue-on-error", probe)
                self.assertEqual(probe["env"]["PYSTACHY_HOME"], "${{ github.workspace }}")
                # (the job's own condition: pr-variants' first test, which names the event; the
                # rest of it, and verification's, is the bootstrap's plan, the same for both)
                job_condition = job["if"].split("&&")[0] if name == "pr-variants" else "True"
                for row in matrix_rows(job, event):
                    # Evaluate only this condition's literal comparisons and boolean operators.
                    condition = "(" + job_condition + ") && (" + probe["if"] + ")"
                    condition = condition.replace("github.event_name", repr(event))
                    condition = condition.replace("matrix.group", repr(row.get("group")))
                    condition = condition.replace("matrix.worker", str(row.get("worker")))  # (a number)
                    condition = condition.replace("&&", " and ").replace("||", " or ")
                    expression = ast.parse(condition, mode="eval")
                    allowed = (ast.Expression, ast.BoolOp, ast.Compare, ast.Constant, ast.And, ast.Or, ast.Eq)
                    self.assertTrue(all(isinstance(node, allowed) for node in ast.walk(expression)), condition)
                    if eval(compile(expression, "<program-cache condition>", "eval"), {"__builtins__": {}}, {}):
                        selected.append((name, row.get("machine"), row.get("group"), row.get("worker")))
            expected = [("pr-variants", None, None, "0")] if event == "pull_request" else [
                ("verification", "x86_64", "runtime-cache", None), ("verification", "aarch64", "runtime-cache", None)]
            with self.subTest(event=event):
                self.assertCountEqual(selected, expected)
            uploads = [step for step in jobs["pr-variants"]["steps"] if step.get("uses", "").startswith("actions/upload-artifact")
                       and "build/program-cache-checks.json" in step["with"]["path"]]
            self.assertEqual(len(uploads), 1)


if __name__ == "__main__":
    unittest.main()
