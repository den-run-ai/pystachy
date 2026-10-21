# pyfiglet's figlet_format(), Figlet and FigletFont on the edge cases its port met: what the font
# parser reads from each embedded font (the end marks, which the parser removes, are also the
# '@' glyph's own characters), justification and direction, among them a direction pyfiglet does
# not know (the property Figlet.justify is then None), wrapping at blanks and inside words at widths
# around a glyph's, widths too small for a glyph, 2**63 - 1, new lines, tabs and returns, text
# with Latin-1 and Latin Extended-A letters (str holds UTF-8 in Pystachy), text made with chr()
# (below 256 one byte in Pystachy) and characters the fonts lack, str() of a font, a missing font,
# and that error escaping as CPython reports it. Each part is a function, so that the fonts it
# loads are garbage when it returns: make verify's gc-stress stage collects at every allocation,
# and each collection scans what is live.
from pyfiglet import (DEFAULT_FONT, CharNotPrinted, Figlet, FigletFont, FontNotFound,
                      __version__, figlet_format)


def show(title: str, art: str) -> None:
    print("== %s: %d lines, %d characters" % (title, art.count("\n"), len(art)))
    for line in art.split("\n"):
        print(repr(line))


def parsed_fonts() -> None:
    # header fields, comment, glyph counts, widths, and a glyph with '@' inside
    for name in ["standard", "slant", "small"]:
        ff = FigletFont(name)
        codes = sorted(ff.chars.keys())
        rows = 0
        for c in codes:
            rows += len("".join(ff.chars[c]))
        print(name, ff.height, ff.hardBlank, ff.printDirection, ff.smushMode, len(ff.comment),
              len(codes), codes[0], codes[-1], sum(ff.width.values()), rows)
        print("  ", ff.comment[:40])
        print("  ", [c in ff.chars
                     for c in [196, 214, 220, 228, 246, 252, 223, 0x104, 0x17E, 0xCA0]])
        print("  ", ff.width[64], ff.chars[64], str(ff), "%s" % ff)


def justify_and_direction() -> None:
    for justify in ["auto", "left", "center", "right", "middle"]:
        show("small justify=" + justify,
             figlet_format("Hi", font="small", justify=justify, width=40))
    for direction in ["right-to-left", "sideways"]:
        show("slant direction=" + direction,
             figlet_format("abc", font="slant", direction=direction))
        show("  justify=left", figlet_format("abc", font="slant", direction=direction,
                                             justify="left"))
    show("sideways right", Figlet(font="small", direction="sideways", justify="right",
                                  width=30).renderText("ok"))
    for f in [Figlet(), Figlet(font="slant", direction="right-to-left"),
              Figlet(direction="sideways"), Figlet(justify="center")]:
        print("properties:", f.direction, f.justify)


def wrapping() -> None:
    # at blanks, right to left and right-justified, and inside a word without blanks
    show("rtl wrap", figlet_format("one two three four", font="slant", width=45,
                                   direction="right-to-left", justify="right"))
    show("center wrap", figlet_format("wrap me around please", font="small", width=40,
                                      justify="center"))
    show("long word", figlet_format("abcdefghijklmnop", font="slant", width=30))
    f = Figlet()
    for width in [9, 10, 11, 12, 20, 9223372036854775807]:
        f.width = width
        art = f.renderText("MiM")
        print("MiM width", width, art.count("\n"), len(art))
    for width in [8, 0, -5]:
        f.width = width
        try:
            f.renderText("M")
        except CharNotPrinted as e:
            print("CharNotPrinted at width %d: %s" % (width, e))


def text_without_glyphs() -> None:
    # new lines, tabs and returns, blanks, nothing
    show("new lines", figlet_format("ab\ncd", font="small"))
    show("tab and returns", figlet_format("a\tb\r\nc\n\nd", font="small"))
    show("blanks", figlet_format("   "))
    show("empty", figlet_format(""))


def letters() -> None:
    # Latin-1 and Latin Extended-A letters, and characters no font has
    show("latin-1", figlet_format("Äpfel ß é"))
    show("latin ext", figlet_format("ŁódźŻółć ĄĘ", width=200))
    show("small umlauts", figlet_format("ÄÖÜ äöü ß", font="small", width=100))
    show("not in font", figlet_format("a€b\U0001F600日本c", font="slant"))


def chr_text() -> None:
    # text made with chr(), which below 256 is one byte in Pystachy: every glyph the standard font
    # has above '~', and bytes that start no UTF-8 sequence (Latin-1 lead bytes before ASCII, a
    # lead byte before another, cut short at the end, C1 and continuation bytes, above 0xF4)
    f = Figlet(width=300)
    art = f.renderText("".join([chr(c) for c in sorted(f.Font.chars.keys()) if c > 126]))
    print("chr extended", art.count("\n"), len(art), art.count("|"), art.count("/"), art.count("_"))
    text = ("a" + chr(0xC4) + "b" + chr(0xFC) + chr(0xDF) + chr(0xE0) + "c" + chr(0x85) +
            chr(0xA0) + chr(0xE4) + chr(0xF6) + chr(0xF4))
    show("chr bytes", f.renderText(text))


def printable_ascii() -> None:
    # every printable ASCII character, each font
    text = "".join([chr(i) for i in range(32, 127)])
    art = ""
    for name in ["standard", "slant", "small"]:
        art = figlet_format(text, font=name, width=300)
        print(name, "ascii", art.count("\n"), len(art), art.count("|"), art.count("/"))
    show("small ascii", art)


def set_font() -> None:
    # one Figlet object, its font changed
    f = Figlet(font="slant", width=60, justify="right")
    show("slant right", f.renderText("set"))
    f.setFont(font="small")
    show("small right", f.renderText("set"))
    f.setFont()
    print(f.font, f.width, f.Font.height)


def missing_font() -> None:
    for name in ["nosuchfont", "../etc/passwd", ""]:
        try:
            Figlet(font=name)
        except FontNotFound as e:
            print("FontNotFound: %r" % str(e))


print(__version__, DEFAULT_FONT)
parsed_fonts()
justify_and_direction()
wrapping()
text_without_glyphs()
letters()
chr_text()
printable_ascii()
set_font()
missing_font()

# the error escapes as CPython reports it
figlet_format("x", font="nosuchfont")
