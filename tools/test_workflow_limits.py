"""Every job of every workflow has a time limit of at most 15 minutes (docs/testing.md#continuous-integration).

CI's groups target under ten minutes of work, within a 15-minute limit that leaves room for slower
runners and for diagnosing a failure; a part that needs more is sharded, not given a longer limit
(#562). Without a limit a job may run for GitHub's default of 360 minutes. The release workflow's jobs
keep limits of their own, which the test holds them to: its prepare job waits up to 20 minutes for CI
on the release commit (tools/release_gate.py --wait-seconds 1200).

Run with python3 -m unittest discover -s tools -p test_workflow_limits.py.
"""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 15
OWN = {"release.yml": {"prepare": 25, "binaries": 25, "container": 25, "publish": 20}}


def jobs(text: str) -> dict:
    """{job: its timeout-minutes, or None}: the top-level jobs of a workflow, read from its lines (the
    workflows here indent by two spaces, so a job's own keys are four deep, and its steps' deeper)."""
    out: dict = {}
    job = None
    section = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.match(r"([A-Za-z_-]+):", line)
        if top:
            section, job = top.group(1), None
            continue
        if section != "jobs":
            continue
        m = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*(#.*)?", line)
        if m:
            job = m.group(1)
            out[job] = None
            continue
        m = re.fullmatch(r"    timeout-minutes:\s*(.+?)\s*(#.*)?", line)
        if m and job is not None:
            out[job] = int(m.group(1)) if m.group(1).isdigit() else m.group(1)
    return out


def workflows() -> dict:
    found = {}
    for path in sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))):
        with open(path, encoding="utf-8") as f:
            found[os.path.basename(path)] = jobs(f.read())
    return found


class ParseTests(unittest.TestCase):
    def test_jobs(self):
        text = (
            "name: X\non:\n  push:\njobs:\n  a:\n    runs-on: u\n    timeout-minutes: 15\n    steps:\n"
            "      - run: x\n        timeout-minutes: 99\n# a comment\n  b-2:   # the second\n    runs-on: u\n"
            "  c:\n    timeout-minutes: ${{ inputs.t }}\nenv:\n  d:\n    timeout-minutes: 1\n"
        )
        # a step's limit is not its job's; d is not a job
        self.assertEqual(jobs(text), {"a": 15, "b-2": None, "c": "${{ inputs.t }}"})


class LimitTests(unittest.TestCase):
    def test_found(self):
        found = workflows()
        self.assertIn("ci.yml", found)
        self.assertIn("verification", found["ci.yml"])

    def test_limits(self):
        over = []
        for name, js in workflows().items():
            for job, minutes in js.items():
                allowed = OWN.get(name, {}).get(job, LIMIT)
                if not isinstance(minutes, int) or minutes > allowed or (allowed > LIMIT and minutes != allowed):
                    over.append(f"{name}: {job}: timeout-minutes {minutes}, where {allowed} is the limit")
        self.assertEqual(over, [], "shard a job that needs more (docs/testing.md#continuous-integration)")

    def test_own_limits_current(self):
        found = workflows()
        for name, js in OWN.items():
            for job in js:
                self.assertIn(job, found.get(name, {}), f"{name}: no job {job} (OWN is stale)")


if __name__ == "__main__":
    unittest.main()
