# Named escapes decode at compile time; explicit code points are independent values.
def show(label: str, value: str) -> None:
    print(label, len(value), ascii(value))


official = "\N{BULLET}\N{bullet}\N{Latin Small Letter E With Acute}"
assert official == "\u2022\u2022\u00e9"
show("official", official)
aliases = "\N{BYTE ORDER MARK}\N{LF}\N{NBSP}\N{ZWJ}\N{NUL}\N{LINE FEED}"
assert aliases == "\ufeff\n\u00a0\u200d\0\n"
show("aliases", aliases)
show("bmp-and-supplementary", "\N{SNOWMAN}\N{GRINNING FACE}")
assert "\N{SNOWMAN}\N{GRINNING FACE}" == "\u2603\U0001f600"

cjk = "\N{CJK UNIFIED IDEOGRAPH-4E00}\N{cjk unified ideograph-4e0a}"
cjk += "\N{CJK UNIFIED IDEOGRAPH-2EBF0}"
assert cjk == "\u4e00\u4e0a\U0002ebf0"
show("cjk", cjk)
hangul = "\N{HANGUL SYLLABLE GA}\N{hangul syllable hih}"
assert hangul == "\uac00\ud7a3"
show("hangul", hangul)
tangut = "\N{TANGUT IDEOGRAPH-17000}\N{TANGUT IDEOGRAPH-187F7}"
assert tangut == "\U00017000\U000187f7"
show("tangut", tangut)
nushu = "\N{NUSHU CHARACTER-1B170}\N{nushu character-1B2FB}"
assert nushu == "\U0001b170\U0001b2fb"
show("nushu", nushu)
khitan = "\N{KHITAN SMALL SCRIPT CHARACTER-18B00}\N{KHITAN SMALL SCRIPT CHARACTER-18CD5}"
assert khitan == "\U00018b00\U00018cd5"
show("khitan", khitan)

# Raw and escaped backslashes must not invoke name lookup.
show("raw", r"\N{BULLET}")
print("raw-bytes", rb"\N{BULLET}")
show("two-backslashes", "\\N{BULLET}")
show("four-backslashes", "\\\\N{BULLET}")
show("three-backslashes", "\\\N{BULLET}")

x = 7
BULLET = "field"
show("f-expression", f"\N{BULLET}{x}")
show("f-escaped-braces", f"{{\N{BULLET}}}")
show("f-escaped-backslash", f"\\N{x}")
show("raw-f-expression", rf"\N{BULLET}")
show("raw-f-braces", rf"\N{{BULLET}}")
show("f-literal-in-expression", f"{'\N{BULLET}'}")
show("f-format-fill", f"{x:\N{MIDDLE DOT}>3}")
