"""Reading budgets, metadata updates and safe event handling."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

import check_submission as check

ISSUE = "## Problem\nA supported input fails.\n## Scope\nA small repro.\n## Done when\nThe repro passes."
PR = "## Problem\nA supported input fails.\n## Change\nPreserve the value.\n## Validation\nRegression passed."


class FormatTests(unittest.TestCase):
    def test_filled_issue_and_pr(self):
        self.assertEqual(check.validate("Preserve values", ISSUE), [])
        self.assertEqual(check.validate("Preserve values", PR, True), [])

    def test_title_boundary_and_empty(self):
        self.assertEqual(check.validate("x" * 64, ISSUE), [])
        for title in ("", " ", "x" * 65, "first\nsecond", "first\rsecond"):
            with self.subTest(title=title):
                self.assertTrue(check.validate(title, ISSUE))

    def test_word_boundary_including_tables_code_and_details(self):
        count = len(ISSUE.split())
        body = ISSUE + " extra" * (200 - count)
        self.assertEqual(check.validate("Small change", body), [])
        for extra in (" word", "\n```\ncode\n```", "\n| table |", "\n<details>hidden</details>"):
            with self.subTest(extra=extra):
                self.assertTrue(check.validate("Small change", body + extra))

    def test_no_whitespace_and_hidden_comment_size_limits(self):
        self.assertTrue(check.validate("Small change", ISSUE + "x" * 6000))
        self.assertTrue(check.validate("Small change", ISSUE + "<!--" + "x" * 6000 + "-->"))
        self.assertEqual(check.validate("Small change", ISSUE + "<!-- guidance " + "word " * 210 + "-->"), [])

    def test_empty_missing_reordered_duplicate_and_hidden_sections(self):
        for body in ("", ISSUE.replace("A small repro.", "<!-- fill this -->"),
                     ISSUE.replace("A small repro.", "_No response_"),
                     ISSUE.replace("## Scope", "## Other"), ISSUE + "\n## Scope\nDuplicate",
                     "<!--" + ISSUE + "-->", "```markdown\n" + ISSUE + "\n```"):
            with self.subTest(body=body):
                self.assertTrue(check.validate("Small change", body))

    def test_code_headings_are_not_sections(self):
        for fence in ("```", "~~~~"):
            body = ISSUE.replace("A small repro.", fence + "\n## Fake\nx = 1\n" + fence)
            self.assertEqual(check.validate("Small change", body), [])

    def test_fence_with_info_string_does_not_close_a_code_block(self):
        body = "## Problem\nReal problem.\n## Scope\n```\nx\n```python\n## Done when\nHidden heading.\n```"
        self.assertTrue(check.validate("Small change", body))

    def test_templates_need_answers(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / ".github/ISSUE_TEMPLATE").glob("*.md"):
            self.assertTrue(check.validate("Example", path.read_text()))
        self.assertTrue(check.validate("Example", (root / ".github/pull_request_template.md").read_text(), True))


class EventTests(unittest.TestCase):
    def current(self, body=ISSUE):
        return {"state": "open", "title": "Small change", "body": body, "head": {"sha": "live-head"}}

    def test_pr_uses_live_metadata_and_head_not_stale_event(self):
        with patch.object(check, "api", side_effect=[self.current(PR), None]) as api:
            self.assertEqual(check.check({"pull_request": {"number": 12, "body": "stale"}}), [])
        self.assertEqual(api.call_args_list[0].args, ("GET", "/pulls/12"))
        self.assertEqual(api.call_args.args[:2], ("POST", "/statuses/live-head"))
        self.assertEqual(api.call_args.args[2]["state"], "success")
        self.assertEqual(api.call_args.args[2]["context"], "Submission format")

    def test_opened_pr_receives_nonblocking_reminder(self):
        event = {"action": "opened", "pull_request": {"number": 12}}
        with patch.object(check, "api", side_effect=[self.current(PR), None, [], None]) as api:
            self.assertEqual(check.check(event), [])
        self.assertEqual(api.call_args_list[2].args[1], "/issues/12/comments?per_page=100")
        self.assertEqual(api.call_args_list[3].args[1], "/issues/12/comments")
        self.assertIn("AI: none", api.call_args_list[3].args[2]["body"])

    def test_opened_pr_rerun_does_not_duplicate_reminder(self):
        event = {"action": "opened", "pull_request": {"number": 12}}
        with patch.object(check, "api", side_effect=[self.current(PR), None,
                                                     [{"body": check.ACK_BODY}]]) as api:
            self.assertEqual(check.check(event), [])
        self.assertEqual(api.call_count, 3)

    def test_invalid_pr_reports_failure(self):
        with patch.object(check, "api", side_effect=[self.current(""), None]) as api:
            self.assertTrue(check.check({"pull_request": {"number": 12}}))
        self.assertEqual(api.call_args.args[2]["state"], "failure")

    def test_invalid_issue_creates_label_without_comments_or_replacing_labels(self):
        with patch.object(check, "api", side_effect=[self.current(""), None, {}, None]) as api:
            self.assertTrue(check.check({"issue": {"number": 3}}))
        self.assertEqual(api.call_args.args, ("POST", "/issues/3/labels", {"labels": [check.LABEL]}))
        self.assertEqual(api.call_args_list[2].args[1], "/labels")
        self.assertFalse(any("comments" in call.args[1] for call in api.call_args_list))

    def test_existing_label_is_reused_and_valid_issue_removes_only_our_label(self):
        with patch.object(check, "api", side_effect=[self.current(""), {}, None]) as api:
            check.check({"issue": {"number": 3}})
        self.assertEqual(len(api.call_args_list), 3)
        with patch.object(check, "api", side_effect=[self.current(), None]) as api:
            self.assertEqual(check.check({"issue": {"number": 3}}), [])
        self.assertEqual(api.call_args.args, ("DELETE", "/issues/3/labels/needs-description"))
        self.assertEqual(api.call_args.kwargs, {"missing_ok": True})

    def test_concurrent_label_creation_and_other_errors(self):
        conflict = urllib.error.HTTPError("url", 422, "exists", {}, None)
        with patch.object(check, "api", side_effect=[self.current(""), None, conflict, {}, None]):
            self.assertTrue(check.check({"issue": {"number": 3}}))
        with patch.object(check, "api", side_effect=[self.current(""), None, conflict, None]):
            with self.assertRaises(urllib.error.HTTPError):
                check.check({"issue": {"number": 3}})

    def test_closed_items_are_not_changed(self):
        with patch.object(check, "api", return_value={"state": "closed"}) as api:
            self.assertEqual(check.check({"issue": {"number": 3}}), [])
        self.assertEqual(api.call_count, 1)

    def test_api_serializes_metadata_as_data_and_preserves_failures(self):
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "example/repo", "GITHUB_TOKEN": "test"}):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value.read.return_value = b'{}'
                check.api("POST", "/statuses/head", {"body": "$(false)\n`command`"})
            request = urlopen.call_args.args[0]
            self.assertEqual(json.loads(request.data), {"body": "$(false)\n`command`"})
            missing = urllib.error.HTTPError("url", 404, "missing", {}, None)
            with patch("urllib.request.urlopen", side_effect=missing):
                self.assertIsNone(check.api("GET", "/labels/missing", missing_ok=True))
                with self.assertRaises(urllib.error.HTTPError):
                    check.api("POST", "/statuses/head", {})


if __name__ == "__main__":
    unittest.main()
