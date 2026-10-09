import sys
k = len(sys.argv)
words = ["the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog", "and", "then", "it", "turns", "to", "take", "a", "nap", "there"]
parts = []
x = 7 * k
for i in range(200000):
    x = (x * 1103515245 + 12345) % 2147483648
    parts.append(words[x % len(words)])
text = " ".join(parts)
t = 0
for i in range(20):
    t += len(text.replace("the lazy dog", "THE LAZY DOG")) + len(text.replace("then it", "after")) + text.count("there and then")
print(t)
