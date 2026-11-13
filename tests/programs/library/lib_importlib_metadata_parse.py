# importlib.metadata's messages: how a METADATA file's lines become headers and a Description,
# as CPython's email parser reads them: folded values and their indentation, line endings
# (and the characters that end no line), a missing separator, lines that are no headers, and
# "From " lines.
from importlib.metadata import metadata

for name in ["crlf-pkg", "cr-pkg", "nosep-pkg", "odd-pkg", "from-pkg", "onlyfrom", "nometa", "noversion", "multi", "upper-pkg",
             "sep-pkg", "fold-pkg"]:
    message = metadata(name)
    print(name, len(message))
    for key, value in message.items():
        print("   ", repr(key), repr(value))
odd = metadata("odd-pkg")
print(odd.get_all("x-mixed"), odd["X-MIXED"], odd.get("no-value") == "", "Spaced" in odd, "After" in odd)
print([key for key in odd])
