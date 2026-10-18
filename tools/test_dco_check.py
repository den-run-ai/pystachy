"""The one-time DCO certification check of tools/dco_check.py, without network access."""
import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

import dco_check

HEADER = "# comment lines and examples:\n#   @github-login Full Name <email>\n"


class SignersTests(unittest.TestCase):
    def test_lines_name_a_login_a_person_and_an_email(self):
        text = (HEADER + "@ada-l Ada Lovelace <ada@example.com>\n"
                "@Bob Bob B <bob@example.com> for Example Corp\n")
        self.assertEqual(dco_check.signers(text), {"ada-l", "bob"})

    def test_lines_without_a_name_or_email_and_comments_do_not_count(self):
        text = HEADER + "@carol <carol@example.com>\n@dave Dave\n # @erin Erin <erin@example.com>\n"
        self.assertEqual(dco_check.signers(text), set())

    def test_the_signers_file_of_the_repository_parses(self):
        with open(os.path.join(os.path.dirname(dco_check.__file__), "..", dco_check.SIGNERS),
                  encoding="utf-8") as f:
            dco_check.signers(f.read())


class PullCopyTests(unittest.TestCase):
    def test_a_missing_file_reads_as_empty(self):
        missing = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        with mock.patch.object(dco_check.urllib.request, "urlopen", side_effect=missing):
            self.assertEqual(dco_check.pull_copy("o/r", "abc", "t"), "")

    def test_other_errors_fail_the_check(self):
        denied = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        with mock.patch.object(dco_check.urllib.request, "urlopen", side_effect=denied):
            with self.assertRaises(urllib.error.HTTPError):
                dco_check.pull_copy("o/r", "abc", "t")

    def test_the_file_is_read_raw_at_the_pull_request_head(self):
        def reply(request, timeout):
            self.assertEqual(request.full_url,
                             "https://api.github.com/repos/o/r/contents/.github/dco-signers.txt?ref=abc")
            self.assertEqual(request.get_header("Accept"), "application/vnd.github.raw+json")
            return io.BytesIO(b"@ada Ada <ada@example.com>\n")

        with mock.patch.object(dco_check.urllib.request, "urlopen", side_effect=reply):
            self.assertEqual(dco_check.pull_copy("o/r", "abc", "t"), "@ada Ada <ada@example.com>\n")


class MainTests(unittest.TestCase):
    def check(self, on_main, in_pull):
        """main() for a pull request by @ada: (exit status, output, whether the API was asked)."""
        with tempfile.TemporaryDirectory() as folder:
            os.mkdir(os.path.join(folder, ".github"))
            with open(os.path.join(folder, dco_check.SIGNERS), "w", encoding="utf-8") as f:
                f.write(HEADER + on_main)
            event = os.path.join(folder, "event.json")
            with open(event, "w", encoding="utf-8") as f:
                json.dump({"pull_request": {"user": {"login": "Ada"}, "head": {"sha": "abc"}}}, f)
            env = {"GITHUB_EVENT_PATH": event, "GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"}
            out = io.StringIO()
            cwd = os.getcwd()
            os.chdir(folder)
            try:
                with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out), \
                        mock.patch.object(dco_check, "pull_copy", return_value=HEADER + in_pull) as api:
                    status = dco_check.main()
            finally:
                os.chdir(cwd)
        return status, out.getvalue(), api.called

    def test_an_author_listed_on_main_passes_without_asking_the_api(self):
        self.assertEqual(self.check("@ada Ada L <ada@example.com>\n", "")[0::2], (0, False))

    def test_a_first_pull_request_that_adds_the_line_passes(self):
        self.assertEqual(self.check("", "@ada Ada L <ada@example.com> for Example Corp\n")[0], 0)

    def test_an_author_listed_nowhere_fails_with_the_line_to_add(self):
        status, out, _ = self.check("@bob Bob <bob@example.com>\n", "@bob Bob <bob@example.com>\n")
        self.assertEqual(status, 1)
        self.assertIn("@Ada Your Name <your-email>", out)


if __name__ == "__main__":
    unittest.main()
