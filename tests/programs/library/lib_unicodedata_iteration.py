# Iteration passes complete code points to unicodedata, including combining marks.
import unicodedata

try:
    print([unicodedata.combining(c) for c in "\u00e9"])
except TypeError as e:
    print("TypeError:", e)
print([unicodedata.combining(c) for c in "abc"])
print([unicodedata.combining(c) for c in "é中🚀e\u0301"])
