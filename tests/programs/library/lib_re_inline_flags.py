# Non-ASCII invalid inline flags use str.isalpha(), not identifier-start classification (#295).
# Cover both directions of the difference, BMP/astral characters, unchanged letters/nonletters,
# ASCII underscore and escaped tokens in all three parser error paths. CPython records the .out.
import re


for char in ["\u2160", "\u2118", "\u1885", "\u037a", "\u0e33", "\ufdfa", "\U00010140",
             "\U00010400", "\u00e9", "\u0301", "_", "1", "!", "z", r"\w"]:
    for prefix, suffix in [("(?i", ")"), ("(?-", ":x)"), ("(?-i", ":x)")]:
        pattern = prefix + char + suffix
        try:
            re.compile(pattern)
            print("unexpected success", repr(pattern))
        except re.error as error:
            print(repr(pattern), error.msg, error.pos)
