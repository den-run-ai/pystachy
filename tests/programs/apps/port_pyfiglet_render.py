# pyfiglet's rendering: the cases of its own test (pyfiglet/test.py of pyfiglet 1.0.4, which
# compares pyfiglet's output with the C figlet's for each font) for the three fonts the port
# embeds, run as a program: one word, a text cut at its spaces, a word cut at its last character
# and an explicit new line, rendered by one Figlet object whose font setFont() changes, as
# test.py does, and printed line by line with repr() as its dump() does; then test.py's banners,
# rendered by Figlet() with the default font and its default width of 80.
from pyfiglet import Figlet


def dump(text: str) -> None:
    for line in text.split('\n'):
        print(repr(line))


def check_texts(texts: list[str]) -> None:
    f = Figlet()
    for text in texts:
        for font in ["standard", "slant", "small"]:
            f.setFont(font=font)
            out = f.renderText(text)
            print("== %s %r: %d lines, %d characters" % (font, text, out.count("\n"), len(out)))
            dump(out)


def banner(text: str) -> None:
    print(Figlet().renderText(text))


check_texts([
    "foo",
    "This is a very long text with many spaces and little words",
    "Averylongwordthatwillbecutatsomepoint I hope",
    "line1\nline2",
])
banner("TESTING one word")
banner("TESTING cut at space")
banner("TESTING cut at last char")
banner("TESTING explicit new line")
