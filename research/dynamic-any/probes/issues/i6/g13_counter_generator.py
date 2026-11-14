from collections import Counter

words = ["a", "b", "a"]
print(Counter(w for w in words).most_common())
