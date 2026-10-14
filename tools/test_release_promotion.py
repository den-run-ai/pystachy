"""Repair partial stable promotion without overwriting release assets or versions."""

import subprocess
import unittest
from unittest.mock import patch

from release_promote import promote

COMMIT = "a" * 40
VERSION = "v0.2.0"
REPOSITORY = "den-run-ai/pystachy"
IMAGE = "namespace/pystachy"


class PromotionTests(unittest.TestCase):
    def responses(self, latest=None, **release_changes):
        release = {"draft": False, "prerelease": False, **release_changes}
        ref = {"object": {"type": "commit", "sha": COMMIT}}
        return [release, ref, {"tag_name": latest} if latest else None]

    def test_equal_latest_repairs_interrupted_registry_promotion(self):
        with patch("release_promote.get_json", side_effect=self.responses(VERSION)), patch(
                "release_promote.command", side_effect=["", COMMIT, VERSION, "", "", ""]) as command:
            self.assertTrue(promote(REPOSITORY, VERSION, IMAGE, "test"))
        self.assertEqual(command.call_args_list[-1].args[0],
                         ["gh", "release", "edit", VERSION, "--repo", REPOSITORY, "--latest"])
        self.assertFalse(any("upload" in call.args[0] for call in command.call_args_list))
        self.assertEqual(command.call_args_list[-2].args[0], ["docker", "push", IMAGE + ":latest"])

    def test_older_version_never_replaces_latest(self):
        with patch("release_promote.get_json", side_effect=self.responses("v0.3.0")), patch(
                "release_promote.command") as command:
            self.assertFalse(promote(REPOSITORY, VERSION, IMAGE, "test"))
        command.assert_not_called()

    def test_unpublished_or_prerelease_is_rejected_before_registry_access(self):
        for changes in ({"draft": True}, {"prerelease": True}):
            with self.subTest(changes=changes), patch("release_promote.get_json", side_effect=self.responses(
                    **changes)), patch("release_promote.command") as command, self.assertRaises(RuntimeError):
                promote(REPOSITORY, VERSION, IMAGE, "test")
            command.assert_not_called()

    def test_source_and_version_mismatches_block_promotion(self):
        for revision, label in (("b" * 40, VERSION), (COMMIT, "v0.1.0")):
            with self.subTest(revision=revision, label=label), patch("release_promote.get_json", side_effect=
                    self.responses()), patch("release_promote.command", side_effect=["", revision, label]
                    ) as command, self.assertRaises(RuntimeError):
                promote(REPOSITORY, VERSION, IMAGE, "test")
            self.assertFalse(any("push" in call.args[0] for call in command.call_args_list))

    def test_push_failure_can_be_retried_without_republication(self):
        responses = ["", COMMIT, VERSION, "", subprocess.CalledProcessError(1, ["docker", "push"])]
        with patch("release_promote.get_json", side_effect=self.responses(VERSION)), patch(
                "release_promote.command", side_effect=responses) as command, self.assertRaises(subprocess.CalledProcessError):
            promote(REPOSITORY, VERSION, IMAGE, "test")
        self.assertFalse(any("gh" in call.args[0] for call in command.call_args_list))


if __name__ == "__main__":
    unittest.main()
