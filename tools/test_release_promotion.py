"""Repair partial stable promotion without overwriting release assets or versions."""

import subprocess
import unittest
from unittest.mock import patch

from release_promote import promote

COMMIT = "a" * 40
VERSION = "v0.2.0"
REPOSITORY = "den-run-ai/pystachy"
IMAGE = "namespace/pystachy"
DIGEST = "sha256:" + "c" * 64


class PromotionTests(unittest.TestCase):
    def responses(self, latest=None, **release_changes):
        release = {"draft": False, "prerelease": False, **release_changes}
        ref = {"object": {"type": "commit", "sha": COMMIT}}
        return [release, ref, {"tag_name": latest} if latest else None]

    def test_equal_latest_repairs_interrupted_registry_promotion(self):
        with patch("release_promote.get_json", side_effect=self.responses(VERSION)), patch(
                "release_promote.verified_source", return_value=IMAGE + "@" + DIGEST), patch(
                "release_promote.registry_manifest", return_value={"digest": DIGEST}), patch(
                "release_promote.command", return_value="") as command:
            self.assertTrue(promote(REPOSITORY, VERSION, IMAGE, "test"))
        self.assertEqual(command.call_args_list[-1].args[0],
                         ["gh", "release", "edit", VERSION, "--repo", REPOSITORY, "--latest"])
        self.assertFalse(any("upload" in call.args[0] for call in command.call_args_list))
        self.assertEqual(command.call_args_list[-2].args[0], ["docker", "buildx", "imagetools", "create",
                         "--prefer-index=false", "--tag", IMAGE + ":latest", IMAGE + "@" + DIGEST])
        self.assertFalse(any("pull" in call.args[0] or "tag" in call.args[0] for call in command.call_args_list))

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

    def test_unverified_source_blocks_all_promotion(self):
        with patch("release_promote.get_json", side_effect=self.responses()), patch(
                "release_promote.verified_source", side_effect=RuntimeError("labels mismatch")), patch(
                "release_promote.command") as command, self.assertRaises(RuntimeError):
            promote(REPOSITORY, VERSION, IMAGE, "test")
        command.assert_not_called()

    def test_push_failure_can_be_retried_without_republication(self):
        with patch("release_promote.get_json", side_effect=self.responses(VERSION)), patch(
                "release_promote.verified_source", return_value=IMAGE + "@" + DIGEST), patch(
                "release_promote.command", side_effect=subprocess.CalledProcessError(1, ["docker", "buildx"])) \
                as command, self.assertRaises(subprocess.CalledProcessError):
            promote(REPOSITORY, VERSION, IMAGE, "test")
        self.assertFalse(any("gh" in call.args[0] for call in command.call_args_list))

    def test_changed_index_blocks_github_latest(self):
        with patch("release_promote.get_json", side_effect=self.responses()), patch(
                "release_promote.verified_source", return_value=IMAGE + "@" + DIGEST), patch(
                "release_promote.registry_manifest", return_value={"digest": "sha256:" + "d" * 64}), patch(
                "release_promote.command", return_value="") as command, self.assertRaises(RuntimeError):
            promote(REPOSITORY, VERSION, IMAGE, "test")
        self.assertFalse(any("gh" in call.args[0] for call in command.call_args_list))


if __name__ == "__main__":
    unittest.main()
