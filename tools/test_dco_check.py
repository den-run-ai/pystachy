"""DCO sign-off rules of tools/dco_check.py, on commits shaped as the REST API lists them."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import dco_check

ADA = {"name": "Ada Lovelace", "email": "ada@example.com"}
BOB = {"name": "Bob", "email": "bob@example.com"}


def commit(message, author=ADA, committer=ADA, parents=1, account="User"):
    return {"sha": "0123456789abcdef0123", "parents": [{"sha": "p"}] * parents,
            "author": {"login": "someone", "type": account},
            "commit": {"message": message, "author": author, "committer": committer}}


class SignoffTests(unittest.TestCase):
    def test_a_sign_off_of_the_author_passes(self):
        self.assertEqual(dco_check.unsigned([commit("Fix\n\nSigned-off-by: Ada Lovelace <ada@example.com>\n")]), [])

    def test_a_sign_off_of_the_committer_passes(self):
        signed = commit("Fix\n\nSigned-off-by: Bob <bob@example.com>", committer=BOB)
        self.assertEqual(dco_check.unsigned([signed]), [])

    def test_case_and_spacing_of_the_trailer_do_not_matter(self):
        signed = commit("Fix\n\nsigned-off-by:  ADA LOVELACE <Ada@Example.com>  \r\n")
        self.assertEqual(dco_check.unsigned([signed]), [])

    def test_one_matching_sign_off_among_several_passes(self):
        signed = commit("Fix\n\nSigned-off-by: Bob <bob@example.com>\nSigned-off-by: Ada Lovelace <ada@example.com>")
        self.assertEqual(dco_check.unsigned([signed]), [])

    def test_a_missing_sign_off_fails(self):
        self.assertEqual(dco_check.unsigned([commit("Fix")]),
                         ["0123456789ab (Ada Lovelace <ada@example.com>): no Signed-off-by line"])

    def test_a_sign_off_of_someone_else_fails(self):
        bad = dco_check.unsigned([commit("Fix\n\nSigned-off-by: Bob <bob@example.com>")])
        self.assertEqual(bad, ["0123456789ab (Ada Lovelace <ada@example.com>): "
                               "no Signed-off-by line names its author or committer"])

    def test_name_and_email_must_belong_to_one_person(self):
        mixed = commit("Fix\n\nSigned-off-by: Ada Lovelace <bob@example.com>", committer=BOB)
        self.assertEqual(len(dco_check.unsigned([mixed])), 1)

    def test_a_trailer_quoted_inside_a_line_does_not_count(self):
        quoted = commit("Fix: say Signed-off-by: Ada Lovelace <ada@example.com> in docs")
        self.assertEqual(len(dco_check.unsigned([quoted])), 1)

    def test_merges_and_bot_commits_are_left_out(self):
        self.assertEqual(dco_check.unsigned([commit("Merge main", parents=2), commit("Bump", account="Bot")]), [])

    def test_names_in_the_report_lose_control_characters(self):
        bad = dco_check.unsigned([commit("Fix", author={"name": "x\n::error::y", "email": "e@example.com"})])
        self.assertEqual(bad, ["0123456789ab (x::error::y <e@example.com>): no Signed-off-by line"])


class ApiTests(unittest.TestCase):
    def test_pages_are_read_until_a_short_one(self):
        pages = [[commit("Fix")] * dco_check.PAGE, [commit("Fix")] * 5]
        urls = []

        def reply(request, timeout):
            urls.append(request.full_url)
            return io.BytesIO(json.dumps(pages[len(urls) - 1]).encode())

        with mock.patch.object(dco_check.urllib.request, "urlopen", side_effect=reply):
            commits = dco_check.pull_commits("o/r", 7, "t")
        self.assertEqual(len(commits), dco_check.PAGE + 5)
        self.assertEqual(urls, [f"https://api.github.com/repos/o/r/pulls/7/commits?per_page={dco_check.PAGE}&page={p}"
                                for p in (1, 2)])


class CommandTests(unittest.TestCase):
    def run_check(self, commits):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "commits.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(commits, f)
            return subprocess.run([sys.executable, dco_check.__file__, path], capture_output=True, text=True)

    def test_signed_commits_exit_zero(self):
        done = self.run_check([commit("Fix\n\nSigned-off-by: Ada Lovelace <ada@example.com>")])
        self.assertEqual((done.returncode, done.stdout), (0, "1 commits signed off\n"))

    def test_an_unsigned_commit_exits_one_with_the_remedy(self):
        done = self.run_check([commit("Fix"), commit("Merge", parents=2)])
        self.assertEqual(done.returncode, 1)
        self.assertIn("1 of 2 commits lack a sign-off", done.stdout)
        self.assertIn("git rebase --signoff", done.stdout)

    def test_a_pull_request_opened_before_the_rule_is_not_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "event.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"pull_request": {"number": 1, "commits": 1, "created_at": "2026-10-17T15:51:25Z"}}, f)
            # (no repository or token: the API is not asked)
            env = {"PATH": os.environ.get("PATH", ""), "GITHUB_EVENT_PATH": path}
            done = subprocess.run([sys.executable, dco_check.__file__], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("before the sign-off rule", done.stdout)
        self.assertLess("2026-10-17T15:51:25Z", dco_check.POLICY)
        self.assertLess(dco_check.POLICY, "2026-10-18T13:26:24Z")  # (#672, opened after: checked)


if __name__ == "__main__":
    unittest.main()
