"""Release notes render without hard line breaks and meet docs/writing.md."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import textwrap
import unittest

import release_notes as notes

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "0123456789abcdef0123456789abcdef01234567"
LINK = f"https://github.com/den-run-ai/pystachy/blob/{COMMIT}/docs/install.md"
GOOD = textwrap.dedent(f"""\
    Pystachy v9.9.9-alpha.1 adds one feature and fixes
    two crashes.

    ## A feature

    The feature now works for
    [lists]({LINK}) and tuples.

    - First fix, wrapped
      onto a second line.
    - Second fix.

    | Target | Requires |
    |---|---|
    | Linux | LLVM 18 |

    ```sh
    pystachy run
    demo.py
    ```
    """)


def build(text, **changes):
    options = dict(version="v9.9.9-alpha.1", commit=COMMIT, repository="den-run-ai/pystachy",
                   image="example/pystachy", prerelease=True)
    options.update(changes)
    return notes.render(text, **options)


class UnwrapTests(unittest.TestCase):
    def test_joins_paragraphs_and_list_items_but_keeps_other_blocks(self):
        self.assertEqual(notes.unwrap(GOOD), textwrap.dedent(f"""\
            Pystachy v9.9.9-alpha.1 adds one feature and fixes two crashes.

            ## A feature

            The feature now works for [lists]({LINK}) and tuples.

            - First fix, wrapped onto a second line.
            - Second fix.

            | Target | Requires |
            |---|---|
            | Linux | LLVM 18 |

            ```sh
            pystachy run
            demo.py
            ```
            """))

    def test_is_idempotent_and_normalizes_carriage_returns(self):
        once = notes.unwrap(GOOD.replace("\n", "\r\n"))
        self.assertEqual(once, notes.unwrap(GOOD))
        self.assertEqual(notes.unwrap(once), once)

    def test_keeps_nested_items_hard_breaks_comments_and_indented_code(self):
        text = ("1. Step one\n   continues.\n   - nested\n     item\n2. Step two\n\n"
                "Line with a break  \nnext line\\\nlast\n\n<!-- keep\nthis -->\n\n"
                "    indented code\n    stays\n")
        self.assertEqual(notes.unwrap(text),
                         "1. Step one continues.\n   - nested item\n2. Step two\n\n"
                         "Line with a break  \nnext line\\\nlast\n\n<!-- keep\nthis -->\n\n"
                         "    indented code\n    stays\n")

    def test_keeps_every_line_of_an_indented_code_block(self):
        for text in ("Run:\n\n    print(1)\n    print(2)\n    print(3)\n\n    print(4)\nAfter.\n",
                     "Run:\n\n    - item\n      continuation\n    next\n",
                     "Run:\n\n    code\n    - item\n    more\n",
                     "Run:\n\n    | a | b |\n    plain\n    more\n"):
            with self.subTest(text=text):
                self.assertEqual(notes.unwrap(text), text)
                self.assertEqual(notes.check_text(text), [])

    def test_keeps_display_math_blocks(self):
        text = "Summary.\n\n$$\nE = mc^2\n+ x\n$$\n"
        self.assertEqual(notes.unwrap(text), text)

    def test_keeps_fenced_code_nested_in_a_list_item(self):
        text = "Summary.\n\n1. Run:\n\n    ```python\n    print(1)\n    print(2)\n    ```\n\n2. Done.\n"
        self.assertEqual(notes.unwrap(text), text)
        self.assertEqual(notes.check_text(text), [])

    def test_keeps_setext_underlines_and_tables_without_outer_pipes(self):
        text = ("Summary.\n\nTitle\n=====\n\nIntro line\nwraps.\na | b\n--- | ---\n1 | 2\n3 | 4\n\n"
                "After\nwrap.\n")
        self.assertEqual(notes.unwrap(text), "Summary.\n\nTitle\n=====\n\nIntro line wraps.\n"
                                             "a | b\n--- | ---\n1 | 2\n3 | 4\n\nAfter wrap.\n")
        self.assertEqual(notes.check_text(text), [])

    def test_indented_items_inside_lists_stay_nested_items(self):
        text = "- a\n  - b\n    - c\n      wraps\n\n    - d\n"
        self.assertEqual(notes.unwrap(text), "- a\n  - b\n    - c wraps\n\n    - d\n")

    def test_list_continuation_paragraph_is_not_code(self):
        text = "- Item\n\n    Its second paragraph\n    wraps.\n"
        self.assertEqual(notes.unwrap(text), "- Item\n\n    Its second paragraph wraps.\n")


class CheckTests(unittest.TestCase):
    def errors(self, text):
        return "\n".join(notes.check_text(text))

    def test_good_notes_pass(self):
        self.assertEqual(notes.check_text(GOOD), [])

    def test_titles_headings_and_reserved_sections(self):
        self.assertIn("summary paragraph", self.errors("## Changes\n\nText.\n"))
        self.assertIn("top-level title", self.errors("Summary.\n\n# Pystachy v1\n"))
        self.assertIn("## or ###", self.errors("Summary.\n\n#### Detail\n"))
        self.assertIn("generates it", self.errors("Summary.\n\n## Release assets\n\nx\n"))
        self.assertIn("summary paragraph", self.errors("- A list first.\n"))
        self.assertIn("empty", self.errors("\n\n"))

    def test_links_must_be_absolute_and_pinned(self):
        self.assertIn("absolute https", self.errors("See [install](../install.md).\n"))
        self.assertIn("absolute https", self.errors("See [below](#limits).\n"))
        self.assertIn("absolute https", self.errors("Summary.\n\n[ref]: docs/x.md\n"))
        main = "https://github.com/den-run-ai/pystachy/blob/main/docs/install.md"
        self.assertIn("Pin", self.errors(f"See [install]({main}).\n"))
        self.assertIn("Pin", self.errors(f"See <{main}>.\n"))
        pinned = "https://github.com/den-run-ai/pystachy/tree/v0.4.0/docs"
        self.assertEqual(notes.check_text(f"See [docs]({pinned}) and [#1](https://github.com/x/y/issues/1).\n"), [])

    def test_code_is_not_checked_for_links_or_placeholders(self):
        text = "Run `[x](y.md)` with `TODO`.\n\n```\n[x](y.md) TODO\n```\n"
        self.assertEqual(notes.check_text(text), [])
        self.assertIn("placeholders", self.errors("Summary.\n\nTBD: write this.\n"))

    def test_paragraph_and_total_budgets_count_rendered_words(self):
        url = "https://github.com/den-run-ai/pystachy/issues/1"
        linked = " ".join(f"[w]({url})" for _ in range(notes.PARAGRAPH_WORDS))
        self.assertEqual(notes.check_text(linked + "\n"), [])
        self.assertIn(f"limit {notes.PARAGRAPH_WORDS} words", self.errors(linked + " extra\n"))
        self.assertIn("limit", self.errors("Summary.\n\n- " + "word " * (notes.PARAGRAPH_WORDS + 1) + "\n"))
        many = "\n\n".join(["word " * 50] * (notes.TOTAL_WORDS // 50 + 1))
        self.assertIn("Shorten the notes", self.errors(many + "\n"))
        table = "Summary.\n\n| a | b |\n|---|---|\n" + ("| " + "word " * 100 + " | x |\n") * 10
        self.assertEqual(notes.check_text(table), [])

    def test_raw_html_is_rejected_but_comments_are_allowed(self):
        self.assertIn("raw HTML", self.errors("Summary.\n\n<details>\nx\n</details>\n"))
        self.assertEqual(notes.check_text("Summary.\n\n<!-- reviewer note -->\n"), [])


class RenderTests(unittest.TestCase):
    def test_appends_assets_without_wrapped_lines(self):
        body = build(GOOD)
        self.assertTrue(body.startswith("Pystachy v9.9.9-alpha.1 adds one feature and fixes two crashes.\n"))
        self.assertIn("\n\n## Release assets\n\n", body)
        self.assertIn("`example/pystachy:v9.9.9-alpha.1`", body)
        self.assertIn(f"[`{COMMIT}`](https://github.com/den-run-ai/pystachy/commit/{COMMIT})", body)
        self.assertIn(f"/blob/{COMMIT}/docs/install.md", body)
        self.assertIn("prerelease", body)
        self.assertNotIn("prerelease", build(GOOD, prerelease=False))
        self.assertEqual(notes.unwrap(body), body)
        self.assertEqual(notes.check_text(body.split("\n## Release assets")[0]), [])

    def test_rejects_invalid_notes_and_identities(self):
        with self.assertRaisesRegex(ValueError, "absolute https"):
            build("See [x](y.md).\n")
        for change in ({"version": "0.4.0"}, {"commit": COMMIT[:12]}, {"repository": "pystachy"},
                       {"image": "Example/Pystachy"}, {"image": "pystachy"}, {"image": "a/b`c"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                build(GOOD, **change)
        for image in ("docker.io/my_org/py--stachy", "my__org/pystachy.v2"):
            with self.subTest(image=image):
                self.assertIn(f"`{image}:v9.9.9-alpha.1`", build(GOOD, image=image))


class RefreshTests(unittest.TestCase):
    PUBLISHED = ("Old summary that was\r\nwrapped.\r\n\r\n## Release assets\r\n\r\n"
                 "Docker image: `a/b:v1.0.0`\r\n(linux/amd64).\r\n\r\nSource commit: `abc`.\r\n")

    def test_replaces_curated_text_and_keeps_published_assets(self):
        body = notes.refresh(self.PUBLISHED, "New summary,\nunwrapped.\n")
        self.assertEqual(body, "New summary, unwrapped.\n\n## Release assets\n\n"
                               "Docker image: `a/b:v1.0.0` (linux/amd64).\n\nSource commit: `abc`.\n")

    def test_reflow_keeps_the_published_words(self):
        body = notes.refresh(self.PUBLISHED)
        self.assertTrue(body.startswith("Old summary that was wrapped.\n\n## Release assets\n"))
        self.assertEqual(body.split(), self.PUBLISHED.split())

    def test_prerelease_status_joins_the_kept_assets_only_with_new_notes(self):
        body = notes.refresh(self.PUBLISHED, "Summary.\n", prerelease=True)
        self.assertTrue(body.endswith("Source commit: `abc`.\n\n" + notes.PRERELEASE + "\n"))
        self.assertEqual(notes.refresh(body, "Summary.\n", prerelease=True), body)
        self.assertNotIn(notes.PRERELEASE, notes.refresh(self.PUBLISHED, "Summary.\n"))
        self.assertNotIn(notes.PRERELEASE, notes.refresh(self.PUBLISHED, prerelease=True))
        stated = self.PUBLISHED + "\nPrereleases do not update `latest`.\n"
        self.assertNotIn(notes.PRERELEASE, notes.refresh(stated, "Summary.\n", prerelease=True))

    def test_refuses_bodies_without_assets_and_notes_that_fail_checks(self):
        with self.assertRaisesRegex(ValueError, "no '## Release assets'"):
            notes.refresh("Hand-written body.\n", "Summary.\n")
        with self.assertRaisesRegex(ValueError, "absolute https"):
            notes.refresh(self.PUBLISHED, "See [x](y.md).\n")

    def run_cli(self, current, *extra):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch, "current.json")
            path.write_text(json.dumps(current), encoding="utf-8")
            output = Path(scratch, "out.md")
            with contextlib.redirect_stderr(io.StringIO()):
                status = notes.main(["refresh", "--version", "v0.1.0-alpha.1", "--current", str(path),
                                     "--output", str(output), *extra])
            return status, output.read_text(encoding="utf-8") if output.exists() else None

    def test_cli_refreshes_only_the_named_published_release(self):
        published = {"tagName": "v0.1.0-alpha.1", "isDraft": False, "body": self.PUBLISHED}
        self.assertEqual(self.run_cli(published, "--source", "reflow"), (0, notes.refresh(self.PUBLISHED)))
        self.assertEqual(self.run_cli({**published, "isDraft": True}, "--source", "reflow"), (1, None))
        self.assertEqual(self.run_cli({**published, "tagName": "v0.1.0"}, "--source", "reflow"), (1, None))


class RepositoryTests(unittest.TestCase):
    def test_current_version_notes_meet_the_guide(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        path = ROOT / "docs/releases" / f"{version}.md"
        self.assertEqual(notes.check_text(path.read_text(encoding="utf-8")), [], path)


if __name__ == "__main__":
    unittest.main()
