import sys
k = len(sys.argv)
words = ["the", "of", "and", "to", "in", "a", "is", "that", "for", "it", "as", "was", "with", "be", "by", "on", "not", "he", "this", "are",
         "or", "his", "from", "at", "which", "but", "have", "an", "had", "they", "you", "were", "their", "one", "all", "we", "can", "her",
         "has", "there", "been", "if", "more", "when", "will", "would", "who", "so", "no", "translation", "information", "government"]
parts = []
x = 3 * k
for i in range(100000):
    x = (x * 1103515245 + 12345) % 2147483648
    parts.append(words[(x >> 8) % len(words)])
t = " ".join(parts)
n = 0
for r in range(30):
    n += t.count("he") + t.count("th") + t.count("ion")
    j = t.find("he")
    while j >= 0:
        n += 1
        j = t.find("he", j + 1)
print(n)
