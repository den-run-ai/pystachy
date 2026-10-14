"""Prevent stale, unrelated, or incomplete CI from authorizing publication."""

import unittest
from unittest.mock import patch

from release_gate import REQUIRED_WORKFLOWS, should_promote, validate_version, workflow_states

COMMIT = "a" * 40


def run(name, identifier=1, **changes):
    result = {"id": identifier, "name": name, "head_sha": COMMIT, "head_branch": "main",
              "event": "push", "status": "completed", "conclusion": "success"}
    result.update(changes)
    return result


class ReleaseGateTests(unittest.TestCase):
    def test_latest_never_moves_backwards_or_to_prerelease(self):
        self.assertTrue(should_promote("v0.1.0", None))
        self.assertTrue(should_promote("v0.10.0", "v0.9.0"))
        self.assertFalse(should_promote("v0.1.0", "v0.2.0"))
        self.assertFalse(should_promote("v0.1.0", "v0.1.0"))
        self.assertFalse(should_promote("v0.2.0-alpha.1", "v0.1.0"))
        with self.assertRaises(RuntimeError):
            should_promote("v0.2.0", "unrecognized")

    def test_all_workflows_required(self):
        self.assertEqual(set(workflow_states([], COMMIT).values()), {"pending"})
        self.assertEqual(set(workflow_states([run(n) for n in REQUIRED_WORKFLOWS], COMMIT).values()),
                         {"success"})

    def test_other_commits_branches_and_prs_do_not_count(self):
        for changes in ({"head_sha": "b" * 40}, {"head_branch": "other"}, {"event": "pull_request"}):
            with self.subTest(changes=changes):
                self.assertEqual(workflow_states([run("CI", **changes)], COMMIT)["CI"], "pending")

    def test_newest_run_overrides_stale_success(self):
        states = workflow_states([run("CI", 3, conclusion="failure"), run("CI", 1)], COMMIT)
        self.assertEqual(states["CI"], "failure")
        states = workflow_states([run("CI", 1), run("CI", 2, status="in_progress")], COMMIT)
        self.assertEqual(states["CI"], "pending")

    def test_cancelled_run_blocks(self):
        self.assertEqual(workflow_states([run("CI", conclusion="cancelled")], COMMIT)["CI"], "cancelled")

    def test_new_version_or_draft_can_proceed(self):
        for release in (None, {"draft": True, "target_commitish": COMMIT}):
            with self.subTest(release=release), patch("release_gate.get_json", side_effect=[release, None]):
                validate_version("den-run-ai/pystachy", COMMIT, "v0.1.0", "test")

    def test_unresolved_draft_must_target_exact_source_commit(self):
        for target in ("b" * 40, "main", None):
            with self.subTest(target=target), patch("release_gate.get_json", side_effect=[
                    {"draft": True, "target_commitish": target}, None]), self.assertRaises(RuntimeError):
                validate_version("den-run-ai/pystachy", COMMIT, "v0.1.0", "test")

    def test_published_version_cannot_be_replaced(self):
        with patch("release_gate.get_json", return_value={"draft": False}), self.assertRaises(RuntimeError):
            validate_version("den-run-ai/pystachy", COMMIT, "v0.1.0", "test")

    def test_existing_tag_must_match_release_commit(self):
        ref = {"object": {"type": "commit", "sha": "b" * 40}}
        with patch("release_gate.get_json", side_effect=[None, ref]), self.assertRaises(RuntimeError):
            validate_version("den-run-ai/pystachy", COMMIT, "v0.1.0", "test")

    def test_annotated_tag_resolves_to_exact_commit(self):
        ref = {"object": {"type": "tag", "sha": "c" * 40}}
        tag = {"object": {"type": "commit", "sha": COMMIT}}
        with patch("release_gate.get_json", side_effect=[None, ref, tag]):
            validate_version("den-run-ai/pystachy", COMMIT, "v0.1.0", "test")


if __name__ == "__main__":
    unittest.main()
