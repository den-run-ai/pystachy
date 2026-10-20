# lib/difflib's SequenceMatcher.get_grouped_opcodes() is a generator (#490): its groups of
# opcodes with up to n lines of context, iterated by for and list()
import difflib

a = "one two three four five six seven eight nine ten".split()
b = "one 2 three four five six seven eight nine 10 eleven".split()
sm = difflib.SequenceMatcher(None, a, b)
for group in sm.get_grouped_opcodes(1):
    print(group)
print(list(difflib.SequenceMatcher(None, "abcd", "abxd").get_grouped_opcodes(0)))
print(list(difflib.SequenceMatcher(None, "same", "same").get_grouped_opcodes()))
print(len(list(difflib.SequenceMatcher(None, a, b).get_grouped_opcodes(3))))
