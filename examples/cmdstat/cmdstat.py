"""cmdstat: what a shell history holds, from shlex's tokens.

usage: python3 cmdstat.py [--top N] [--quote] HISTORY
       pystachy build cmdstat.py -o cmdstat && ./cmdstat HISTORY

Each line of HISTORY is split as a POSIX shell splits it, by shlex.shlex(line, posix=True,
punctuation_chars=True) with whitespace_split: quotes and backslashes are undone, and runs of the
operator characters ();<>|& are tokens of their own. The operators that join commands (|, ||, &,
&&, ;) split a line into its simple commands, a redirection (<, >, >>, >& and the like) takes the
word after it, and parentheses are dropped. cmdstat counts the commands by name, the options of
each (its words that start with -), the redirections and the pipelines by length, and reports the
lines whose quotes are not closed (shlex's ValueError) with their numbers. --quote prints each
command of each line instead, its words rejoined by shlex.join(), with the quoting a shell needs and
no more.

shlex's tokens do not say which were quoted: a quoted operator, as in echo '|', is an operator here.
"""
import shlex
import sys


def split_line(line: str) -> list[str]:
    """The tokens of a line, the operators apart (ValueError for an open quote or a trailing \\)."""
    lex = shlex.shlex(line, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def kind(token: str) -> str:
    # "join" for an operator that joins commands, "redirect" for a redirection, "paren" for
    # parentheses, "word" for the others
    if token and token.strip("<>&") == "" and ("<" in token or ">" in token):
        return "redirect"
    if token and token.strip("|&;") == "":
        return "join"
    if token and token.strip("()") == "":
        return "paren"
    return "word"


def commands(tokens: list[str]) -> tuple[list[list[str]], int, int]:
    """The simple commands of a line's tokens (their words, without redirections), the length of
    its longest pipeline and its count of redirections."""
    out: list[list[str]] = []
    words: list[str] = []
    pipe = 0
    longest = 0
    redirects = 0
    target = False
    for token in tokens:
        k = kind(token)
        if target and k == "word":
            target = False  # (the file of a redirection)
        elif k == "redirect":
            redirects += 1
            target = True
        elif k == "join":
            if words:
                out.append(words)
                pipe += 1
                longest = max(longest, pipe)
            words = []
            if token != "|":
                pipe = 0
        elif k == "word":
            words.append(token)
    if words:
        out.append(words)
        longest = max(longest, pipe + 1)
    return out, longest, redirects


def by_count(item: tuple[str, int]) -> tuple[int, str]:
    # the larger counts first, then in alphabetical order
    return (-item[1], item[0])


def report(nlines: int, counts: dict[str, int], options: dict[str, dict[str, int]],
           pipelines: dict[int, int], redirects: int, errors: list[str], top: int) -> list[str]:
    """The report's lines."""
    out = [f"{nlines} lines, {sum(counts.values())} commands, {redirects} redirections, "
           f"{len(errors)} lines with an open quote"]
    out.append("the longest pipeline of a line: " + ", ".join(f"{n} command{'s' if n > 1 else ''} on {pipelines[n]} lines"
                                         for n in sorted(pipelines)))
    out.append(f"the {min(top, len(counts))} commonest of {len(counts)} commands, with their commonest options:")
    for cmd, n in sorted(counts.items(), key=by_count)[:top]:
        opts = sorted(options[cmd].items(), key=by_count)[:4]
        out.append((f"{n:9}  {cmd:10} " + ", ".join(f"{o} {c}" for o, c in opts)).rstrip())
    for e in errors[:5]:
        out.append(f"line {e}")
    if len(errors) > 5:
        out.append(f"... and {len(errors) - 5} more lines with an open quote")
    return out


def main(argv: list[str]) -> int:
    top = 10
    quote = False
    files: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--top" and i + 1 < len(argv) and argv[i + 1].isdigit():
            top = int(argv[i + 1])
            i += 1
        elif argv[i] == "--quote":
            quote = True
        elif argv[i].startswith("-"):
            print(f"cmdstat: unknown option {argv[i]}", file=sys.stderr)
            return 2
        else:
            files.append(argv[i])
        i += 1
    if len(files) != 1:
        print("usage: cmdstat.py [--top N] [--quote] HISTORY", file=sys.stderr)
        return 2
    counts: dict[str, int] = {}
    options: dict[str, dict[str, int]] = {}
    pipelines: dict[int, int] = {}
    redirects = 0
    errors: list[str] = []
    nlines = 0
    out = sys.stdout
    with open(files[0]) as f:
        for line in f:
            nlines += 1
            try:
                tokens = split_line(line)
            except ValueError as e:
                errors.append(f"{nlines}: {e}")
                if quote:
                    print(f"cmdstat: line {nlines}: {e}", file=sys.stderr)
                continue
            cmds, longest, r = commands(tokens)
            if quote:
                for words in cmds:
                    out.write(shlex.join(words) + "\n")
                continue
            redirects += r
            if longest:
                pipelines[longest] = pipelines.get(longest, 0) + 1
            for words in cmds:
                cmd = words[0]
                counts[cmd] = counts.get(cmd, 0) + 1
                if cmd not in options:
                    options[cmd] = {}
                seen = options[cmd]
                for w in words[1:]:
                    if w.startswith("-") and w != "-":
                        seen[w] = seen.get(w, 0) + 1
    if not quote:
        for text in report(nlines, counts, options, pipelines, redirects, errors, top):
            print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
