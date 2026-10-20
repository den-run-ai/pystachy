# error: error: expected str, got int (compiling difflib.SequenceMatcher.__chain_b()
# lib/difflib's SequenceMatcher compares sequences of str (lib/README.md): a str, or a list of
# lines; CPython's takes any sequence of hashable items
import difflib
print(difflib.SequenceMatcher(None, [1, 2, 3], [1, 3]).ratio())
