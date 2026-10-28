"""The scripts parse under macOS's /bin/sh, bash 3.2, as they do under dash and bash 5. Bash 3.2's
lexer finds the end of a command substitution $( ... ) by counting parentheses (parse.y's
parse_matched_pair, which skips quotes, backslash escapes and comments, but knows no case statement or
here-document): the `)` of a case pattern without its optional leading parenthesis, `a) ...` rather
than `(a) ...`, ends the substitution there, and the script fails to parse. These tests find each
substitution as bash 3.2 does, and each inside one as bash 3.2 does when it runs it, and require sh to
parse what each holds."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent.parent
# the scripts make lint's shellcheck checks
SCRIPTS = ("tests/*.sh", "tests/ffi/*.sh", "tools/*.sh", "bench/*.sh")
CLOSE = {"(": ")", "{": "}", "[": "]"}
HEREDOC = re.compile(r"<<(-?)[ \t]*\\?(['\"]?)([A-Za-z0-9_]+)\2")


def matched_pair(text, i, open_, close, found, qc="", command=False, first_close=False, escapes=False):
    """bash 3.2's parse_matched_pair, from TEXT[I] just past OPEN: the index just past the CLOSE that
    ends it. Within double quotes, appends (start, end, opener) to FOUND for what each $( ... ), $(( ... ))
    or ${ ... } holds."""
    count, was_dollar, in_comment, pass_next, start, prev = 1, False, False, False, i, ""
    check_comment = command and qc not in ("`", "'", '"')
    while count:
        while qc != "'" and not pass_next and text.startswith("\\\n", i):   # (shell_getc joins lines)
            i += 2
        if i >= len(text):
            raise SyntaxError(f"unexpected end of file looking for the {close!r} of the {open_!r} at {start}")
        ch = text[i]
        i += 1
        if in_comment:
            in_comment, prev = ch != "\n", ch
            continue
        if check_comment and ch == "#" and (i - 1 == start or prev in " \t\n"):
            in_comment = True
        if pass_next:
            pass_next, prev = False, ch
            continue
        if ch == close:
            count -= 1
        elif open_ == "{" and was_dollar and ch == open_:
            count += 1
        elif not first_close and ch == open_:
            count += 1
        prev = ch
        if open_ == "'":
            pass_next = escapes and ch == "\\"
            continue
        pass_next = ch == "\\"
        if open_ != close:   # (a grouping construct: $( ... ), ${ ... }; what it holds is read when it runs)
            if ch in "'\"`":
                i = matched_pair(text, i, ch, ch, [], qc=ch, escapes=was_dollar and ch == "'")
        elif open_ == '"' and ch == "`":
            i = matched_pair(text, i, "`", "`", [])
        elif open_ != "`" and was_dollar and ch in CLOSE:
            end = matched_pair(text, i, ch, CLOSE[ch], [], first_close=ch == "{")
            found.append((i, end - 1, "((" if text.startswith("(", i) and ch == "(" else ch))
            i = end
        was_dollar = ch == "$"
    return i


def substitutions(text, base=0, prev="\n"):
    """(start, end) of what each $( ... ) of the script TEXT holds, as bash 3.2 delimits it when it reads
    the script, and of each inside one as it delimits it when it runs that one (reading what it holds as
    a script), or expands a ${ ... }: their indexes plus BASE."""
    found, heredocs, i = [], [], 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i, prev = i + 2, "\\"
        elif ch == "'":
            i, prev = text.index("'", i + 1) + 1, ch
        elif ch == "#" and prev in " \t\n;&|()":
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
        elif ch in "\"`":
            i, prev = matched_pair(text, i + 1, ch, ch, found if ch == '"' else [], qc=ch), ch
        elif ch == "$" and text.startswith(("(", "{"), i + 1):
            opened = text[i + 1]
            end = matched_pair(text, i + 2, opened, CLOSE[opened], [], command=opened == "(",
                               first_close=opened == "{")
            found.append((i + 2, end - 1, "((" if text.startswith("((", i + 1) else opened))
            i, prev = end, opened
        elif (match := HEREDOC.match(text, i)) and not text.startswith("<<<", i):
            heredocs.append((match[3], match[1] == "-"))
            i, prev = match.end(), "x"
        elif ch == "\n" and heredocs:   # (here-documents' bodies, which the lexer reads by lines)
            i += 1
            for delimiter, tabs in heredocs:
                while i < len(text):
                    end = text.find("\n", i)
                    end = len(text) if end < 0 else end
                    line, i = text[i:end], end + 1
                    if (line.lstrip("\t") if tabs else line) == delimiter:
                        break
            heredocs, prev = [], "\n"
        else:
            i, prev = i + 1, ch
    result = []
    for start, end, opened in found:
        if opened != "((":   # (an arithmetic expansion)
            result += [(base + start, base + end)] if opened == "(" else []
            result += substitutions(text[start:end], base + start, "\n" if opened == "(" else "x")
    return result


def unparsed(text):
    """Each $( ... ) of the script TEXT that bash 3.2 ends where sh does not: (line, what it holds)."""
    try:
        found = substitutions(text)
    except SyntaxError as error:
        return [(0, str(error))]
    bad = []
    for start, end in found:
        held = text[start:end]
        result = subprocess.run(["sh", "-n", "-c", held], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            bad.append((text.count("\n", 0, start) + 1, held))
    return bad


class Bash32Tests(unittest.TestCase):
    def test_every_substitution_ends_where_sh_ends_it(self):
        scripts = sorted({path for pattern in SCRIPTS for path in ROOT.glob(pattern)})
        self.assertIn(ROOT / "tests/verify.sh", scripts)
        for path in scripts:
            with self.subTest(script=str(path.relative_to(ROOT))):
                self.assertEqual(unparsed(path.read_text()), [],
                                 "bash 3.2 ends these substitutions early: give each case pattern "
                                 "inside $( ... ) its leading parenthesis, (pattern)")
        # (the scanner finds them: tests/verify.sh holds the most of any script)
        self.assertGreater(len(substitutions((ROOT / "tests/verify.sh").read_text())), 150)

    def test_a_case_pattern_without_its_parenthesis_ends_a_substitution(self):
        for cut, whole in (
                ('n=$(echo 1 | while read -r p; do case $s in *" $p "*) ;; *) echo "$p" ;; esac; done)\n',
                 'n=$(echo 1 | while read -r p; do case $s in (*" $p "*) ;; (*) echo "$p" ;; esac; done)\n'),
                ('f=$(\n  case $k in\n    sigint) grep -l x "$@" ;;\n    *) echo ;;\n  esac | sed -n 1p)\n',
                 'f=$(\n  case $k in\n    (sigint) grep -l x "$@" ;;\n    (*) echo ;;\n  esac | sed -n 1p)\n'),
                ('x="$(case a in a) echo ;; esac)"\n', 'x="$(case a in (a) echo ;; esac)"\n'),
                ('x=${y:-$(case a in a) echo ;; esac)}\n', 'x=${y:-$(case a in (a) echo ;; esac)}\n'),
                ('x=$( (case a in a) echo ;; esac) )\n', 'x=$( (case a in (a) echo ;; esac) )\n'),
                ('x=$(echo $(case a in a) echo ;; esac))\n', 'x=$(echo $(case a in (a) echo ;; esac))\n')):
            with self.subTest(text=cut):
                self.assertNotEqual(unparsed(cut), [])
                self.assertEqual(unparsed(whole), [])
        # (a case outside a substitution, or as a word, needs no parenthesis)
        self.assertEqual(unparsed('case a in a) x=$(echo case a in a) ;; esac\n'), [])

    def test_quotes_comments_escapes_arithmetic_and_here_documents(self):
        # (their parentheses do not count, but those of a here-document in a substitution do)
        text = ('a=$(echo ")" \\) \')\' # )\n)\nb=$((1 + (2)))\nc=$(cat <<\'EOF\'\n()\nEOF\n)\n'
                'cat <<EOF\n)\nEOF\nd="$(echo "$(echo \')\')")"\ne=`echo ")"`\n')
        self.assertEqual([text[start:end] for start, end in substitutions(text)],
                         ['echo ")" \\) \')\' # )\n', "cat <<'EOF'\n()\nEOF\n", 'echo "$(echo \')\')"',
                          "echo ')'"])
        self.assertEqual(unparsed(text), [])
        self.assertNotEqual(unparsed(text.replace("()\nEOF", "(\nEOF")), [])


if __name__ == "__main__":
    unittest.main()
