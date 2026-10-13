"""re_bench: textwrap's regular expressions (CPython 3.13's patterns), timed.

usage: python3 tools/re_bench.py [--time] [--cpu]
       pystachy build tools/re_bench.py -o re_bench && ./re_bench --time

It makes 200 paragraphs of about 470 characters and 200 blocks of 15 indented lines, from a linear
congruential generator, and prints a checksum of what the patterns make of them: the split of a
paragraph into words and spaces (wordsep_re, and wordsep_simple_re, of break_on_hyphens=False),
and dedent()'s substitutions and findall(). With --time, it prints each operation's time per call,
the median of 5 rounds over all the inputs: each call reads a str of its own. tools/re_probe.py
--time runs it with CPython and compiled; tools/re_probe.py counts what lib/re does for
inputs(20), 20 paragraphs and 20 blocks made the same way.
--cpu uses process CPU time for timings, excluding scheduling waits on a busy host.
"""
import re
import sys
import time

WORDSEP = '\n        ( # any whitespace\n          [\\\t\\\n\\\x0b\\\x0c\\\r\\ ]+\n        | # em-dash between words\n          (?<=[\\w!"\\\'&.,?]) -{2,} (?=\\w)\n        | # word, possibly hyphenated\n          [^\\\t\\\n\\\x0b\\\x0c\\\r\\ ]+? (?:\n            # hyphenated word\n              -(?: (?<=[^\\d\\W]{2}-) | (?<=[^\\d\\W]-[^\\d\\W]-))\n              (?= [^\\d\\W] -? [^\\d\\W])\n            | # end of word\n              (?=[\\\t\\\n\\\x0b\\\x0c\\\r\\ ]|\\Z)\n            | # em-dash\n              (?<=[\\w!"\\\'&.,?]) (?=-{2,}\\w)\n            )\n        )'
WORDSEP_SIMPLE = '([\\\t\\\n\\\x0b\\\x0c\\\r\\ ]+)'
WHITESPACE_ONLY = '^[ \t]+$'
LEADING_WHITESPACE = '(^[ \t]*)(?:[^ \t\n])'

seed = 20261013


def rand(n: int) -> int:
    # an int in [0, n): a 31-bit linear congruential generator
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed >> 8) % n


WORDS = ["the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog", "well-known", "e-mail",
         "re-entrant", "--", "it's", "(see", "below),", "a", "of", "and", "self-evident.", "text"]


def paragraph(n: int) -> str:
    return " ".join([WORDS[rand(len(WORDS))] for _ in range(n)])


def block(lines: int) -> str:
    out: list[str] = []
    for _ in range(lines):
        indent = "    " if rand(4) else "      "
        out.append("" if rand(6) == 0 else ("   " if rand(8) == 0 else indent + paragraph(4)))
    return "\n".join(out) + "\n"


def inputs(n: int) -> tuple[list[str], list[str]]:
    # n paragraphs and n blocks, the same on every call
    global seed
    seed = 20261013
    return [paragraph(80) for _ in range(n)], [block(15) for _ in range(n)]


def main() -> None:
    wordsep = re.compile(WORDSEP, re.VERBOSE)
    simple = re.compile(WORDSEP_SIMPLE)
    only = re.compile(WHITESPACE_ONLY, re.MULTILINE)
    leading = re.compile(LEADING_WHITESPACE, re.MULTILINE)
    margin = re.compile(r"(?m)^    ")
    paras, blocks = inputs(200)
    check = 0
    for p in paras:
        check += len(wordsep.split(p)) + 2 * len(simple.split(p))
    for b in blocks:
        check += len(only.sub("", b)) + len(leading.findall(b)) + len(margin.sub("", b))
    print("checksum", check)
    if "--time" in sys.argv:
        cpu = "--cpu" in sys.argv
        for name in ["wordsep_re.split", "wordsep_simple_re.split", "whitespace_only_re.sub", "leading_whitespace_re.findall", "margin.sub"]:
            best: list[float] = []
            for _ in range(5):
                t = time.process_time() if cpu else time.perf_counter()
                if name == "wordsep_re.split":
                    for p in paras:
                        wordsep.split(p)
                elif name == "wordsep_simple_re.split":
                    for p in paras:
                        simple.split(p)
                elif name == "whitespace_only_re.sub":
                    for b in blocks:
                        only.sub("", b)
                elif name == "leading_whitespace_re.findall":
                    for b in blocks:
                        leading.findall(b)
                else:
                    for b in blocks:
                        margin.sub("", b)
                elapsed = (time.process_time() if cpu else time.perf_counter()) - t
                best.append(elapsed / 200 * 1e6)
            best.sort()
            print(f"{name:30} {best[2]:8.2f} us")


if __name__ == "__main__":
    main()
