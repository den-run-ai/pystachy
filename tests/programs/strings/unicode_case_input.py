# Text read at run time groups by case as it does under CPython: lower() and casefold() keys,
# upper() and title() of each word, and the case tests (#120).
import sys

folded: dict[str, int] = {}
lowered: dict[str, list[str]] = {}
for line in sys.stdin:
    for word in line.split():
        key = word.casefold()
        folded[key] = folded.get(key, 0) + 1
        lowered.setdefault(word.lower(), []).append(word)
        print(word, word.upper(), word.title(), word.capitalize(), word.swapcase(), word.isupper(), word.islower(),
              word.istitle())
print(sorted(folded.items()))
print(sorted(lowered.items()))
print(len(folded), len(lowered), "strasse" in folded, "école" in lowered, "οδός" in lowered)
