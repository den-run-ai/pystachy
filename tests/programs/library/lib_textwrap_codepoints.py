# Text wrapping and shortening use character widths and preserve UTF-8 sequences.
import textwrap

print(textwrap.wrap("aa ää-ää", 7))
print(textwrap.wrap("Grüße aus Köln", 9))
print(textwrap.shorten("Grüße aus Köln, sagt sie.", 15))

lines = textwrap.wrap("ééé", 3)
print([len(s) for s in lines], "".join(lines) == "ééé")
