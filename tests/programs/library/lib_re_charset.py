# Reusing a Pattern's ASCII character-class tables must preserve all class encodings, negation,
# categories, scoped flags and Unicode case folding. Interleave ASCII with non-ASCII searches,
# then revisit the ASCII strings and the same pattern from a nested replacement function.
import re

PATTERNS = [
    r"[a-z0-9]+",
    r"[^a-z0-9]+",
    r"[aefijkpquvz]+",
    r"[\w!\"'&.,?]+",
    r"[^\d\W]+",
    r"[\s\d]+",
    r"[^\s\d]+",
    r"[a\u0100\u0200\u0300\u0400\u0500]+",
    r"(?i)[a-z]+",
    r"(?ai)[a-z]+",
    r"(?i)[A-\u0100]+",
    r"(?i:[a-z]+)(?-i:[A-Z]+)",
    r"(?i:[a-z]+)|(?a:\w+)",
    r"(?<=[a-z])[A-Z](?=[0-9])",
    r"(?:[a-z]+|[0-9]+|[^\w])",
    r"[a-z]+?[0-9]",
    r"[a-z]++[0-9]",
]
ASCII = "".join([chr(i) for i in range(128)])
TEXTS = [ASCII, "abc ABC aB1 !&.,? \t\r\n 123", "éÉKſİı\u0100\u0200\u0300\u0400\u0500１２３", "AbC1 -- aZ2"]
for p in PATTERNS:
    rx = re.compile(p)
    print(repr(p))
    for _ in range(2):
        for t in TEXTS:
            print(rx.findall(t))
    print(rx.sub("<>", "AbC1 -- aZ2\nhello WORLD 123"))
    print(rx.split("AbC1 -- aZ2\nhello WORLD 123"))

words = re.compile(r"[a-z]+")


def nested(m: re.Match) -> str:
    return "[" + ",".join(words.findall((m.group(0) or "") + " XYZ again")) + "]"


print(words.sub(nested, "one two three"))
re.purge()
print(words.findall("four FIVE six"))
